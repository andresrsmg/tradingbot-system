#!/usr/bin/env python3
"""
Bot de Futures Trading ETH/USDT (5x alavancagem)
Estratégia: Breakout + Momentum
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
        logging.FileHandler('eth_futures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ETHFuturesBot:
    def __init__(self, leverage=5):
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
        
        # Configuração FUTURES ETH
        self.symbol = 'ETH/USDT:USDT'  # Perpetual contract
        self.leverage = leverage  # 5x alavancagem (moderado para ETH)
        self.timeframe = '15m'  # Timeframe médio para ETH
        self.position_size = 0.35  # 35% do capital
        self.stop_loss = 0.012  # 1.2%
        self.take_profit = 0.025  # 2.5%
        
        # Estado
        self.in_position = False
        self.position_side = None  # 'long' ou 'short'
        self.entry_price = 0
        self.position_amount = 0
        self.total_pnl = 0
        
        logger.info("="*60)
        logger.info("🔷 BOT DE FUTURES TRADING ETH INICIADO")
        logger.info("="*60)
        logger.info(f"Alavancagem: {self.leverage}x")
        logger.info(f"Position size: {self.position_size*100}% do capital")
        logger.info(f"Stop-loss: {self.stop_loss*100}% | Take-profit: {self.take_profit*100}%")
        logger.info(f"Timeframe: {self.timeframe}")
    
    def get_market_data(self):
        """Buscar dados ETH"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Indicadores para ETH (breakout)
            df['ema12'] = df['close'].ewm(span=12).mean()
            df['ema26'] = df['close'].ewm(span=26).mean()
            df['macd'] = df['ema12'] - df['ema26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            df['rsi'] = self.calculate_rsi(df['close'], period=14)
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # Volume
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            
            return df
        except Exception as e:
            logger.error(f"Erro dados ETH: {e}")
            return None
    
    def calculate_rsi(self, prices, period=14):
        """RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def generate_eth_signal(self, df):
        """Sinal para ETH (breakout + momentum)"""
        if df is None or len(df) < 30:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # MACD signals
        macd_bullish = latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']
        macd_bearish = latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']
        
        # RSI conditions
        overbought = latest['rsi'] > 70
        oversold = latest['rsi'] < 30
        
        # Bollinger Bands
        bb_breakout_up = latest['close'] > latest['bb_upper']
        bb_breakout_down = latest['close'] < latest['bb_lower']
        bb_middle_touch = abs(latest['close'] - latest['bb_middle']) / latest['bb_middle'] < 0.005
        
        # Volume confirmation
        high_volume = latest['volume_ratio'] > 1.3
        
        if not self.in_position:
            # Sinal LONG (breakout up + MACD bullish)
            long_conditions = [
                macd_bullish,
                not overbought,
                latest['rsi'] > 50,
                bb_breakout_up or (bb_middle_touch and latest['close'] > latest['bb_middle']),
                high_volume,
            ]
            
            if sum(long_conditions) >= 3:
                return 'LONG'
            
            # Sinal SHORT (breakout down + MACD bearish)
            short_conditions = [
                macd_bearish,
                not oversold,
                latest['rsi'] < 50,
                bb_breakout_down or (bb_middle_touch and latest['close'] < latest['bb_middle']),
                high_volume,
            ]
            
            if sum(short_conditions) >= 3:
                return 'SHORT'
        
        # Condições de SAÍDA
        if self.in_position:
            if self.position_side == 'long':
                exit_conditions = [
                    macd_bearish,  # MACD virou
                    overbought,  # Sobrecomprado
                    latest['close'] < latest['bb_middle'],  # Volta para média
                    latest['rsi'] < 50,  # Momentum negativo
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_LONG'
                    
            elif self.position_side == 'short':
                exit_conditions = [
                    macd_bullish,  # MACD virou
                    oversold,  # Sobrevendido
                    latest['close'] > latest['bb_middle'],  # Volta para média
                    latest['rsi'] > 50,  # Momentum positivo
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_SHORT'
        
        return None
    
    def execute_eth_trade(self, signal):
        """Executar trade ETH"""
        try:
            # Obter saldo futures
            balance = self.exchange.fetch_balance()
            free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
            
            # Para ETH, usar apenas 25% do capital total
            eth_capital = free_usdt * 0.25
            
            if signal == 'LONG':
                if eth_capital < 15:  # Mínimo $15 para ETH
                    logger.warning("Capital ETH insuficiente para LONG")
                    return False
                
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                # Capital alavancado
                leveraged_capital = eth_capital * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_eth = amount_usd / current_price
                
                # Arredondar para contrato ETH (0.01 mínimo)
                amount_eth = round(amount_eth, 4)
                
                if amount_eth < 0.01:
                    logger.warning(f"Quantidade muito baixa: {amount_eth} ETH")
                    return False
                
                logger.info(f"🚀 EXECUTANDO ETH FUTURES LONG: {amount_eth} ETH (${amount_usd:.2f})")
                logger.info(f"   Alavancagem: {self.leverage}x | Capital ETH: ${eth_capital:.2f}")
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='buy',
                    amount=amount_eth
                )
                
                self.in_position = True
                self.position_side = 'long'
                self.entry_price = float(order['average'])
                self.position_amount = amount_eth
                
                logger.info(f"✅ ETH FUTURES LONG EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.2f}")
                logger.info(f"   Quantidade: {self.position_amount} ETH")
                logger.info(f"   Valor: ${self.position_amount * self.entry_price:.2f}")
                
                return True
                
            elif signal == 'SHORT':
                if eth_capital < 15:
                    logger.warning("Capital ETH insuficiente para SHORT")
                    return False
                
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                leveraged_capital = eth_capital * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_eth = amount_usd / current_price
                amount_eth = round(amount_eth, 4)
                
                logger.info(f"🚀 EXECUTANDO ETH FUTURES SHORT: {amount_eth} ETH (${amount_usd:.2f})")
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='sell',
                    amount=amount_eth
                )
                
                self.in_position = True
                self.position_side = 'short'
                self.entry_price = float(order['average'])
                self.position_amount = amount_eth
                
                logger.info(f"✅ ETH FUTURES SHORT EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.2f}")
                
                return True
                
            elif signal in ['CLOSE_LONG', 'CLOSE_SHORT']:
                logger.info(f"🔄 FECHANDO POSIÇÃO ETH FUTURES: {self.position_side.upper()}")
                
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
                
                logger.info(f"✅ POSIÇÃO ETH FUTURES FECHADA!")
                logger.info(f"   Preço: ${exit_price:.2f}")
                logger.info(f"   PnL: ${pnl:.4f} ({pnl_pct:+.2f}%)")
                logger.info(f"   PnL Total ETH: ${self.total_pnl:.4f}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ETH trade: {e}")
            return False
    
    def check_eth_limits(self):
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
            logger.info(f"🎯 ETH TAKE-PROFIT ATINGIDO: +{pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_eth_trade(signal)
        
        # Stop-loss
        elif pnl_pct <= -self.stop_loss * 100:
            logger.info(f"🛑 ETH STOP-LOSS ATINGIDO: {pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_eth_trade(signal)
    
    def run(self):
        """Loop principal ETH"""
        logger.info("🔷 INICIANDO ETH FUTURES TRADING")
        
        trade_count = 0
        max_trades_per_day = 8  # ETH tem mais oportunidades
        
        while True:
            try:
                # Verificar SL/TP
                self.check_eth_limits()
                
                # Obter dados
                df = self.get_market_data()
                
                if df is not None:
                    # Gerar sinal
                    signal = self.generate_eth_signal(df)
                    
                    if signal:
                        logger.info(f"📡 SINAL ETH: {signal}")
                        
                        # Executar trade
                        if self.execute_eth_trade(signal):
                            trade_count += 1
                            logger.info(f"🎯 ETH TRADES HOJE: {trade_count}/{max_trades_per_day}")
                    
                    # Status atual
                    balance = self.exchange.fetch_balance()
                    free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
                    
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    
                    logger.info(f"📊 ETH STATUS: ${free_usdt * 0.25:.2f} alocado para ETH")
                    logger.info(f"📈 ETH: ${ticker['last']:.2f} ({ticker['percentage']:.2f}%)")
                    
                    if self.in_position:
                        current_price = ticker['last']
                        if self.position_side == 'long':
                            current_pnl = (current_price - self.entry_price) / self.entry_price * 100
                        else:
                            current_pnl = (self.entry_price - current_price) / self.entry_price * 100
                        
                        logger.info(f"💰 ETH POSIÇÃO: {self.position_side.upper()} {self.position_amount} ETH")
                        logger.info(f"   PnL atual: {current_pnl:+.2f}%")
                    
                    logger.info(f"💰 ETH PnL TOTAL: ${self.total_pnl:.4f}")
                    logger.info("-" * 40)
                
                # Aguardar 3 minutos (ETH tem timeframe menor)
                time.sleep(180)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot ETH interrompido")
                break
            except Exception as e:
                logger.error(f"❌ Erro ETH: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = ETHFuturesBot(leverage=5)
    bot.run()