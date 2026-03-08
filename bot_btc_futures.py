#!/usr/bin/env python3
"""
Bot de Futures Trading BTC/USDT (3x alavancagem)
Estratégia: Trend Following + Mean Reversion
"""

import ccxt
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('btc_futures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BTCFuturesBot:
    def __init__(self, leverage=3):
        # Configuração da API BYBIT (mesma do SOL)
        self.api_key = 'WUaurGbHS0s6cnIlCb'
        self.secret_key = 'CRuJS9fQZauSS3LsC6Ez79atRWHY1x7r1r1c'
        
        # Exchange Bybit FUTURES
        self.exchange = ccxt.bybit({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'options': {'defaultType': 'future'},
            'enableRateLimit': True
        })
        
        # Configuração FUTURES BTC
        self.symbol = 'BTC/USDT:USDT'  # Perpetual contract
        self.leverage = leverage  # 3x alavancagem (conservador para BTC)
        self.timeframe = '1h'  # Timeframe maior para BTC
        self.position_size = 0.4  # 40% do capital (mais conservador)
        self.stop_loss = 0.01  # 1% (BTC é menos volátil)
        self.take_profit = 0.02  # 2% (mais conservador)
        
        # Estado
        self.in_position = False
        self.position_side = None  # 'long' ou 'short'
        self.entry_price = 0
        self.position_amount = 0
        self.total_pnl = 0
        
        logger.info("="*60)
        logger.info("⚡ BOT DE FUTURES TRADING BTC INICIADO")
        logger.info("="*60)
        logger.info(f"Alavancagem: {self.leverage}x")
        logger.info(f"Position size: {self.position_size*100}% do capital")
        logger.info(f"Stop-loss: {self.stop_loss*100}% | Take-profit: {self.take_profit*100}%")
        logger.info(f"Timeframe: {self.timeframe}")
    
    def get_market_data(self):
        """Buscar dados BTC"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Indicadores para BTC (trend following)
            df['ema20'] = df['close'].ewm(span=20).mean()
            df['ema50'] = df['close'].ewm(span=50).mean()
            df['ema200'] = df['close'].ewm(span=200).mean()
            df['rsi'] = self.calculate_rsi(df['close'], period=14)
            
            # ADX para força da tendência
            df['adx'] = self.calculate_adx(df, period=14)
            
            # ATR para stop-loss dinâmico
            df['atr'] = self.calculate_atr(df, period=14)
            
            # Volume profile
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            return df
        except Exception as e:
            logger.error(f"Erro dados BTC: {e}")
            return None
    
    def calculate_rsi(self, prices, period=14):
        """RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_adx(self, df, period=14):
        """ADX - Average Directional Index"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smooth
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def calculate_atr(self, df, period=14):
        """ATR - Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def generate_btc_signal(self, df):
        """Sinal para BTC (trend following + mean reversion)"""
        if df is None or len(df) < 50:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Tendência de longo prazo
        trend_up = latest['ema20'] > latest['ema50'] > latest['ema200']
        trend_down = latest['ema20'] < latest['ema50'] < latest['ema200']
        
        # Força da tendência (ADX)
        strong_trend = latest['adx'] > 25
        
        # Condições de sobrecompra/sobrevenda
        overbought = latest['rsi'] > 70
        oversold = latest['rsi'] < 30
        
        # Volume confirmation
        high_volume = latest['volume_ratio'] > 1.5
        
        if not self.in_position:
            # Sinal LONG (trend up + pullback)
            long_conditions = [
                trend_up,  # Tendência de alta
                not overbought,  # Não sobrecomprado
                latest['rsi'] > 50,  # Momentum positivo
                strong_trend,  # Tendência forte
                high_volume,  # Volume confirmando
            ]
            
            if sum(long_conditions) >= 4:
                return 'LONG'
            
            # Sinal SHORT (trend down + bounce)
            short_conditions = [
                trend_down,  # Tendência de baixa
                not oversold,  # Não sobrevendido
                latest['rsi'] < 50,  # Momentum negativo
                strong_trend,  # Tendência forte
                high_volume,  # Volume confirmando
            ]
            
            if sum(short_conditions) >= 4:
                return 'SHORT'
        
        # Condições de SAÍDA
        if self.in_position:
            if self.position_side == 'long':
                exit_conditions = [
                    latest['ema20'] < latest['ema50'],  # Reversão de tendência
                    overbought,  # Sobrecomprado
                    latest['rsi'] < 50,  # Momentum virou
                    not strong_trend,  # Tendência enfraqueceu
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_LONG'
                    
            elif self.position_side == 'short':
                exit_conditions = [
                    latest['ema20'] > latest['ema50'],  # Reversão de tendência
                    oversold,  # Sobrevendido
                    latest['rsi'] > 50,  # Momentum virou
                    not strong_trend,  # Tendência enfraqueceu
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_SHORT'
        
        return None
    
    def execute_btc_trade(self, signal):
        """Executar trade BTC"""
        try:
            # Obter saldo futures
            balance = self.exchange.fetch_balance()
            free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
            
            # Para BTC, usar apenas 30% do capital total (já que temos múltiplos pares)
            btc_capital = free_usdt * 0.3
            
            if signal == 'LONG':
                if btc_capital < 20:  # Mínimo $20 para BTC
                    logger.warning("Capital BTC insuficiente para LONG")
                    return False
                
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                # Capital alavancado
                leveraged_capital = btc_capital * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_btc = amount_usd / current_price
                
                # Arredondar para contrato BTC (0.001 mínimo)
                amount_btc = round(amount_btc, 6)
                
                if amount_btc < 0.001:
                    logger.warning(f"Quantidade muito baixa: {amount_btc} BTC")
                    return False
                
                logger.info(f"🚀 EXECUTANDO BTC FUTURES LONG: {amount_btc} BTC (${amount_usd:.2f})")
                logger.info(f"   Alavancagem: {self.leverage}x | Capital BTC: ${btc_capital:.2f}")
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='buy',
                    amount=amount_btc
                )
                
                self.in_position = True
                self.position_side = 'long'
                self.entry_price = float(order['average'])
                self.position_amount = amount_btc
                
                logger.info(f"✅ BTC FUTURES LONG EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.2f}")
                logger.info(f"   Quantidade: {self.position_amount} BTC")
                logger.info(f"   Valor: ${self.position_amount * self.entry_price:.2f}")
                
                return True
                
            elif signal == 'SHORT':
                if btc_capital < 20:
                    logger.warning("Capital BTC insuficiente para SHORT")
                    return False
                
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                leveraged_capital = btc_capital * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_btc = amount_usd / current_price
                amount_btc = round(amount_btc, 6)
                
                logger.info(f"🚀 EXECUTANDO BTC FUTURES SHORT: {amount_btc} BTC (${amount_usd:.2f})")
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='sell',
                    amount=amount_btc
                )
                
                self.in_position = True
                self.position_side = 'short'
                self.entry_price = float(order['average'])
                self.position_amount = amount_btc
                
                logger.info(f"✅ BTC FUTURES SHORT EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.2f}")
                
                return True
                
            elif signal in ['CLOSE_LONG', 'CLOSE_SHORT']:
                logger.info(f"🔄 FECHANDO POSIÇÃO BTC FUTURES: {self.position_side.upper()}")
                
                side = 'sell' if self.position_side == 'long' else 'buy'
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side=side,
                    amount=self.position_amount
                )
                
                exit_price = float(order['average'])
                
                # Calcular PnL
                if self.position_side == 'long':
                    pnl = (exit_price - self.entry_price) * self.position_amount
                else:
                    pnl = (self.entry_price - exit_price) * self.position_amount
                
                pnl_pct = (pnl / (self.position_amount * self.entry_price)) * 100
                
                self.total_pnl += pnl
                self.in_position = False
                
                logger.info(f"✅ POSIÇÃO BTC FUTURES FECHADA!")
                logger.info(f"   Preço: ${exit_price:.2f}")
                logger.info(f"   PnL: ${pnl:.4f} ({pnl_pct:+.2f}%)")
                logger.info(f"   PnL Total BTC: ${self.total_pnl:.4f}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro BTC trade: {e}")
            return False
    
    def check_btc_limits(self):
        """Verificar stop-loss e take-profit"""
        if not self.in_position:
            return
        
        ticker = self.exchange.fetch_ticker(self.symbol)
        current_price = ticker['last']
        
        if self.position_side == 'long':
            pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        else:
            pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
        
        # Take-profit
        if pnl_pct >= self.take_profit * 100:
            logger.info(f"🎯 BTC TAKE-PROFIT ATINGIDO: +{pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_btc_trade(signal)
        
        # Stop-loss
        elif pnl_pct <= -self.stop_loss * 100:
            logger.info(f"🛑 BTC STOP-LOSS ATINGIDO: {pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_btc_trade(signal)
    
    def run(self):
        """Loop principal BTC"""
        logger.info("⚡ INICIANDO BTC FUTURES TRADING")
        
        trade_count = 0
        max_trades_per_day = 5  # Menos trades para BTC (timeframe maior)
        
        while True:
            try:
                # Verificar SL/TP
                self.check_btc_limits()
                
                # Obter dados
                df = self.get_market_data()
                
                if df is not None:
                    # Gerar sinal
                    signal = self.generate_btc_signal(df)
                    
                    if signal:
                        logger.info(f"📡 SINAL BTC: {signal}")
                        
                        # Executar trade
                        if self.execute_btc_trade(signal):
                            trade_count += 1
                            logger.info(f"🎯 BTC TRADES HOJE: {trade_count}/{max_trades_per_day}")
                    
                    # Status atual
                    balance = self.exchange.fetch_balance()
                    free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
                    
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    
                    logger.info(f"📊 BTC STATUS: ${free_usdt * 0.3:.2f} alocado para BTC")
                    logger.info(f"📈 BTC: ${ticker['last']:.2f} ({ticker['percentage']:.2f}%)")
                    
                    if self.in_position:
                        current_price = ticker['last']
                        if self.position_side == 'long':
                            current_pnl = (current_price - self.entry_price) / self.entry_price * 100
                        else:
                            current_pnl = (self.entry_price - current_price) / self.entry_price * 100
                        
                        logger.info(f"💰 BTC POSIÇÃO: {self.position_side.upper()} {self.position_amount} BTC")
                        logger.info(f"   PnL atual: {current_pnl:+.2f}%")
                    
                    logger.info(f"💰 BTC PnL TOTAL: ${self.total_pnl:.4f}")
                    logger.info("-" * 40)
                
                # Aguardar 5 minutos (BTC tem timeframe maior)
                time.sleep(300)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot BTC interrompido")
                break
            except Exception as e:
                logger.error(f"❌ Erro BTC: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = BTCFuturesBot(leverage=3)
    bot.run()