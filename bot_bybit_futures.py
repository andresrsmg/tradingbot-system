#!/usr/bin/env python3
"""
Bot de Futures Trading Bybit (10x-25x alavancagem)
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
        logging.FileHandler('bybit_futures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BybitFuturesBot:
    def __init__(self, leverage=10):
        # Configuração da API BYBIT
        self.api_key = 'WUaurGbHS0s6cnIlCb'
        self.secret_key = 'CRuJS9fQZauSS3LsC6Ez79atRWHY1x7r1r1c'
        
        # Exchange Bybit FUTURES
        self.exchange = ccxt.bybit({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'options': {'defaultType': 'future'},
            'enableRateLimit': True
        })
        
        # Configuração FUTURES
        self.symbol = 'SOL/USDT:USDT'  # Perpetual contract
        self.leverage = leverage  # 10x alavancagem inicial
        self.timeframe = '5m'
        self.position_size = 0.6  # 60% do capital (com alavancagem)
        self.stop_loss = 0.015  # 1.5% (apertado com alavancagem)
        self.take_profit = 0.03  # 3% (rápido com alavancagem)
        
        # Estado
        self.in_position = False
        self.position_side = None  # 'long' ou 'short'
        self.entry_price = 0
        self.position_amount = 0
        self.total_pnl = 0
        
        logger.info("="*60)
        logger.info("⚡ BOT DE FUTURES TRADING BYBIT INICIADO")
        logger.info("="*60)
        logger.info(f"Alavancagem: {self.leverage}x")
        logger.info(f"Position size: {self.position_size*100}% do capital")
        logger.info(f"Stop-loss: {self.stop_loss*100}% | Take-profit: {self.take_profit*100}%")
        
        # Configurar alavancagem
        self.set_leverage()
    
    def set_leverage(self):
        """Configurar alavancagem na Bybit"""
        try:
            # Bybit usa parâmetros específicos para leverage
            self.exchange.set_leverage(self.leverage, self.symbol)
            logger.info(f"✅ Alavancagem configurada: {self.leverage}x")
        except Exception as e:
            logger.warning(f"⚠️  Não foi possível configurar alavancagem: {e}")
    
    def get_market_data(self):
        """Buscar dados rápidos"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Indicadores avançados para futures
            df['ema9'] = df['close'].ewm(span=9).mean()
            df['ema21'] = df['close'].ewm(span=21).mean()
            df['ema50'] = df['close'].ewm(span=50).mean()
            df['rsi'] = self.calculate_rsi(df['close'], period=14)
            df['macd'], df['signal'], df['histogram'] = self.calculate_macd(df['close'])
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
            
            # Volume profile
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            
            return df
        except Exception as e:
            logger.error(f"Erro dados: {e}")
            return None
    
    def calculate_rsi(self, prices, period=14):
        """RSI rápido"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, prices):
        """MACD para sinais de tendência"""
        exp1 = prices.ewm(span=12).mean()
        exp2 = prices.ewm(span=26).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9).mean()
        histogram = macd - signal
        return macd, signal, histogram
    
    def generate_futures_signal(self, df):
        """Sinal para futures (long/short) com múltiplos indicadores"""
        if df is None or len(df) < 50:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Pontuação para LONG
        long_score = 0
        long_conditions = [
            latest['ema9'] > latest['ema21'] > latest['ema50'],  # +2 pontos
            latest['rsi'] > 50 and latest['rsi'] < 70,  # +1 ponto
            latest['macd'] > latest['signal'],  # +1 ponto
            latest['close'] > latest['bb_middle'],  # +1 ponto
            latest['volume'] > latest['volume_sma'],  # +1 ponto
            latest['close'] > latest['ema21'],  # +1 ponto
        ]
        long_score = sum([2 if i == 0 else 1 for i, cond in enumerate(long_conditions) if cond])
        
        # Pontuação para SHORT
        short_score = 0
        short_conditions = [
            latest['ema9'] < latest['ema21'] < latest['ema50'],  # +2 pontos
            latest['rsi'] < 50 and latest['rsi'] > 30,  # +1 ponto
            latest['macd'] < latest['signal'],  # +1 ponto
            latest['close'] < latest['bb_middle'],  # +1 ponto
            latest['volume'] > latest['volume_sma'],  # +1 ponto
            latest['close'] < latest['ema21'],  # +1 ponto
        ]
        short_score = sum([2 if i == 0 else 1 for i, cond in enumerate(short_conditions) if cond])
        
        # Decisão baseada em pontuação
        if not self.in_position:
            if long_score >= 5 and long_score > short_score:
                return 'LONG'
            elif short_score >= 5 and short_score > long_score:
                return 'SHORT'
        
        # Condições de SAÍDA (se estiver em posição)
        if self.in_position:
            if self.position_side == 'long':
                exit_conditions = [
                    latest['ema9'] < latest['ema21'],  # Reversão
                    latest['rsi'] > 80,  # Sobrecomprado
                    latest['macd'] < latest['signal'],  # MACD negativo
                    latest['close'] < latest['bb_middle'],  # Abaixo da média
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_LONG'
                    
            elif self.position_side == 'short':
                exit_conditions = [
                    latest['ema9'] > latest['ema21'],  # Reversão
                    latest['rsi'] < 20,  # Sobrevendido
                    latest['macd'] > latest['signal'],  # MACD positivo
                    latest['close'] > latest['bb_middle'],  # Acima da média
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_SHORT'
        
        return None
    
    def execute_futures_trade(self, signal):
        """Executar trade com futures"""
        try:
            # Obter saldo futures
            balance = self.exchange.fetch_balance()
            free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
            
            if signal == 'LONG':
                if free_usdt < 10:
                    logger.warning("Saldo futures insuficiente para LONG")
                    return False
                
                # Calcular quantidade com alavancagem
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                # Capital alavancado
                leveraged_capital = free_usdt * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_sol = amount_usd / current_price
                
                # Arredondar para contrato
                amount_sol = round(amount_sol, 3)
                
                if amount_sol < 0.01:
                    logger.warning(f"Quantidade muito baixa: {amount_sol} SOL")
                    return False
                
                logger.info(f"🚀 EXECUTANDO FUTURES LONG: {amount_sol} SOL (${amount_usd:.2f})")
                logger.info(f"   Alavancagem: {self.leverage}x | Capital: ${free_usdt:.2f}")
                
                # Ordem de mercado FUTURES
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='buy',
                    amount=amount_sol
                )
                
                self.in_position = True
                self.position_side = 'long'
                self.entry_price = float(order['average'])
                self.position_amount = amount_sol
                
                logger.info(f"✅ FUTURES LONG EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.4f}")
                logger.info(f"   Quantidade: {self.position_amount} SOL")
                logger.info(f"   Stop-loss: ${self.entry_price * (1 - self.stop_loss):.4f}")
                logger.info(f"   Take-profit: ${self.entry_price * (1 + self.take_profit):.4f}")
                
                return True
                
            elif signal == 'SHORT':
                if free_usdt < 10:
                    logger.warning("Saldo futures insuficiente para SHORT")
                    return False
                
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                leveraged_capital = free_usdt * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_sol = amount_usd / current_price
                amount_sol = round(amount_sol, 3)
                
                logger.info(f"🚀 EXECUTANDO FUTURES SHORT: {amount_sol} SOL (${amount_usd:.2f})")
                logger.info(f"   Alavancagem: {self.leverage}x | Capital: ${free_usdt:.2f}")
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='sell',
                    amount=amount_sol
                )
                
                self.in_position = True
                self.position_side = 'short'
                self.entry_price = float(order['average'])
                self.position_amount = amount_sol
                
                logger.info(f"✅ FUTURES SHORT EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.4f}")
                logger.info(f"   Quantidade: {self.position_amount} SOL")
                logger.info(f"   Stop-loss: ${self.entry_price * (1 + self.stop_loss):.4f}")
                logger.info(f"   Take-profit: ${self.entry_price * (1 - self.take_profit):.4f}")
                
                return True
                
            elif signal in ['CLOSE_LONG', 'CLOSE_SHORT']:
                logger.info(f"🔄 FECHANDO POSIÇÃO FUTURES: {self.position_side.upper()}")
                
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
                else:  # short
                    pnl = (self.entry_price - exit_price) * self.position_amount
                
                pnl_pct = (pnl / (self.position_amount * self.entry_price)) * 100
                
                self.total_pnl += pnl
                self.in_position = False
                
                logger.info(f"✅ POSIÇÃO FUTURES FECHADA!")
                logger.info(f"   Preço: ${exit_price:.4f}")
                logger.info(f"   PnL: ${pnl:.4f} ({pnl_pct:+.2f}%)")
                logger.info(f"   PnL Total: ${self.total_pnl:.4f}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro futures trade: {e}")
            return False
    
    def check_futures_limits(self):
        """Verificar stop-loss e take-profit para futures"""
        if not self.in_position:
            return
        
        ticker = self.exchange.fetch_ticker(self.symbol)
        current_price = ticker['last']
        
        # Calcular PnL atual
        if self.position_side == 'long':
            pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        else:  # short
            pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
        
        # Take-profit
        if pnl_pct >= self.take_profit * 100:
            logger.info(f"🎯 TAKE-PROFIT ATINGIDO: +{pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_futures_trade(signal)
        
        # Stop-loss
        elif pnl_pct <= -self.stop_loss * 100:
            logger.info(f"🛑 STOP-LOSS ATINGIDO: {pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_futures_trade(signal)
    
    def run(self):
        """Loop principal FUTURES"""
        logger.info("⚡ INICIANDO FUTURES TRADING BYBIT")
        
        trade_count = 0
        max_trades_per_day = 10  # Mais trades com futures
        
        while True:
            try:
                # Verificar SL/TP primeiro
                self.check_futures_limits()
                
                # Obter dados
                df = self.get_market_data()
                
                if df is not None:
                    # Gerar sinal
                    signal = self.generate_futures_signal(df)
                    
                    if signal:
                        logger.info(f"📡 SINAL FUTURES: {signal}")
                        
                        # Executar trade
                        if self.execute_futures_trade(signal):
                            trade_count += 1
                            logger.info(f"🎯 TRADES HOJE: {trade_count}/{max_trades_per_day}")
                            
                            if trade_count >= max_trades_per_day:
                                logger.info("⏸️  LIMITE DIÁRIO ATINGIDO. Aguardando...")
                                time.sleep(3600)
                    
                    # Status atual
                    balance = self.exchange.fetch_balance()
                    free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
                    
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    
                    logger.info(f"📊 FUTURES STATUS: ${free_usdt:.2f} USDT livre")
                    logger.info(f"📈 SOL: ${ticker['last']:.2f} ({ticker['percentage']:.2f}%)")
                    
                    if self.in_position:
                        current_price = ticker['last']
                        if self.position_side == 'long':
                            current_pnl = (current_price - self.entry_price) / self.entry_price * 100
                        else:
                            current_pnl = (self.entry_price - current_price) / self.entry_price * 100
                        
                        logger.info(f"💰 POSIÇÃO: {self.position_side.upper()} {self.position_amount} SOL")
                        logger.info(f"   PnL atual: {current_pnl:+.2f}%")
                        logger.info(f"   Valor posição: ${self.position_amount * current_price:.2f}")
                    
                    logger.info(f"💰 PnL TOTAL: ${self.total_pnl:.4f}")
                    logger.info("-" * 40)
                
                # Aguardar 2 minutos (mais rápido para futures)
                time.sleep(120)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot interrompido")
                break
            except Exception as e:
                logger.error(f"❌ Erro: {e}")
                time.sleep(30)

if __name__ == "__main__":
    # Iniciar com 10x alavancagem (seguro)
    bot = BybitFuturesBot(leverage=10)
    bot.run()