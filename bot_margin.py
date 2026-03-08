#!/usr/bin/env python3
"""
Bot de Trading com Margin (3x-5x alavancagem)
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
        logging.FileHandler('margin_trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarginTradingBot:
    def __init__(self, leverage=3):
        # Configuração da API
        self.api_key = 'XnSQojzurcUqBX23mbnH3GFqV4YzvISbfPZyZvbKwsoDuhLNW6Ucld44S4y3hj97'
        self.secret_key = 'F9lD9r7eBkQRUijKuEj6lXYZOMmJTZa2Teoukx0XcLXAiILvL47cuF8wL7DNIiwC'
        
        # Exchange com margin
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'options': {'defaultType': 'margin'},
            'enableRateLimit': True
        })
        
        # Configuração MARGIN
        self.symbol = 'SOL/USDT'
        self.leverage = leverage  # 3x alavancagem
        self.timeframe = '5m'
        self.position_size = 0.7  # 70% do capital margin
        self.stop_loss = 0.02  # 2% (mais apertado com alavancagem)
        self.take_profit = 0.04  # 4% (mais rápido com alavancagem)
        
        # Estado
        self.in_position = False
        self.position_side = None  # 'long' ou 'short'
        self.entry_price = 0
        self.position_amount = 0
        self.total_pnl = 0
        
        logger.info("="*60)
        logger.info("⚡ BOT DE MARGIN TRADING INICIADO")
        logger.info("="*60)
        logger.info(f"Alavancagem: {self.leverage}x")
        logger.info(f"Position size: {self.position_size*100}% do capital")
        logger.info(f"Stop-loss: {self.stop_loss*100}% | Take-profit: {self.take_profit*100}%")
    
    def get_market_data(self):
        """Buscar dados rápidos"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Indicadores para margin
            df['ema9'] = df['close'].ewm(span=9).mean()
            df['ema21'] = df['close'].ewm(span=21).mean()
            df['ema50'] = df['close'].ewm(span=50).mean()
            df['rsi'] = self.calculate_rsi(df['close'], period=14)
            df['macd'], df['signal'], df['histogram'] = self.calculate_macd(df['close'])
            
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
    
    def generate_margin_signal(self, df):
        """Sinal para margin (long/short)"""
        if df is None or len(df) < 30:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Condições para LONG (compra alavancada)
        long_conditions = [
            latest['ema9'] > latest['ema21'] > latest['ema50'],  # Tendência de alta
            latest['rsi'] > 50 and latest['rsi'] < 70,  # Forte mas não sobrecomprado
            latest['macd'] > latest['signal'],  # MACD positivo
            latest['close'] > latest['ema21'],  # Preço acima média
        ]
        
        # Condições para SHORT (venda alavancada)
        short_conditions = [
            latest['ema9'] < latest['ema21'] < latest['ema50'],  # Tendência de baixa
            latest['rsi'] < 50 and latest['rsi'] > 30,  # Forte mas não sobrevendido
            latest['macd'] < latest['signal'],  # MACD negativo
            latest['close'] < latest['ema21'],  # Preço abaixo média
        ]
        
        # Se 3 de 4 condições, entra
        if sum(long_conditions) >= 3 and not self.in_position:
            return 'LONG'
        elif sum(short_conditions) >= 3 and not self.in_position:
            return 'SHORT'
        
        # Condições de SAÍDA (se estiver em posição)
        if self.in_position:
            if self.position_side == 'long':
                exit_conditions = [
                    latest['ema9'] < latest['ema21'],  # Reversão
                    latest['rsi'] > 80,  # Sobrecomprado
                    latest['macd'] < latest['signal'],  # MACD negativo
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_LONG'
                    
            elif self.position_side == 'short':
                exit_conditions = [
                    latest['ema9'] > latest['ema21'],  # Reversão
                    latest['rsi'] < 20,  # Sobrevendido
                    latest['macd'] > latest['signal'],  # MACD positivo
                ]
                if sum(exit_conditions) >= 2:
                    return 'CLOSE_SHORT'
        
        return None
    
    def execute_margin_trade(self, signal):
        """Executar trade com margin"""
        try:
            # Obter saldo margin
            balance = self.exchange.fetch_balance()
            free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
            
            if signal == 'LONG':
                if free_usdt < 20:
                    logger.warning("Saldo margin insuficiente para LONG")
                    return False
                
                # Calcular quantidade com alavancagem
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                # Capital alavancado
                leveraged_capital = free_usdt * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_sol = amount_usd / current_price
                
                # Arredondar
                amount_sol = round(amount_sol, 3)
                
                if amount_sol < 0.01:
                    logger.warning(f"Quantidade muito baixa: {amount_sol} SOL")
                    return False
                
                logger.info(f"🚀 EXECUTANDO MARGIN LONG: {amount_sol} SOL (${amount_usd:.2f})")
                logger.info(f"   Alavancagem: {self.leverage}x | Capital: ${free_usdt:.2f}")
                
                # Ordem de mercado MARGIN
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='buy',
                    amount=amount_sol,
                    params={'marginMode': 'cross'}  # Margin cross
                )
                
                self.in_position = True
                self.position_side = 'long'
                self.entry_price = float(order['average'])
                self.position_amount = amount_sol
                
                logger.info(f"✅ MARGIN LONG EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.4f}")
                logger.info(f"   Quantidade: {self.position_amount} SOL")
                logger.info(f"   Stop-loss: ${self.entry_price * (1 - self.stop_loss):.4f}")
                logger.info(f"   Take-profit: ${self.entry_price * (1 + self.take_profit):.4f}")
                
                return True
                
            elif signal == 'SHORT':
                if free_usdt < 20:
                    logger.warning("Saldo margin insuficiente para SHORT")
                    return False
                
                ticker = self.exchange.fetch_ticker(self.symbol)
                current_price = ticker['last']
                
                leveraged_capital = free_usdt * self.leverage
                amount_usd = leveraged_capital * self.position_size
                amount_sol = amount_usd / current_price
                amount_sol = round(amount_sol, 3)
                
                logger.info(f"🚀 EXECUTANDO MARGIN SHORT: {amount_sol} SOL (${amount_usd:.2f})")
                logger.info(f"   Alavancagem: {self.leverage}x | Capital: ${free_usdt:.2f}")
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side='sell',
                    amount=amount_sol,
                    params={'marginMode': 'cross'}
                )
                
                self.in_position = True
                self.position_side = 'short'
                self.entry_price = float(order['average'])
                self.position_amount = amount_sol
                
                logger.info(f"✅ MARGIN SHORT EXECUTADO!")
                logger.info(f"   Preço: ${self.entry_price:.4f}")
                logger.info(f"   Quantidade: {self.position_amount} SOL")
                logger.info(f"   Stop-loss: ${self.entry_price * (1 + self.stop_loss):.4f}")
                logger.info(f"   Take-profit: ${self.entry_price * (1 - self.take_profit):.4f}")
                
                return True
                
            elif signal in ['CLOSE_LONG', 'CLOSE_SHORT']:
                logger.info(f"🔄 FECHANDO POSIÇÃO MARGIN: {self.position_side.upper()}")
                
                side = 'sell' if self.position_side == 'long' else 'buy'
                
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='market',
                    side=side,
                    amount=self.position_amount,
                    params={'marginMode': 'cross'}
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
                
                logger.info(f"✅ POSIÇÃO FECHADA!")
                logger.info(f"   Preço: ${exit_price:.4f}")
                logger.info(f"   PnL: ${pnl:.4f} ({pnl_pct:+.2f}%)")
                logger.info(f"   PnL Total: ${self.total_pnl:.4f}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro margin trade: {e}")
            return False
    
    def check_margin_limits(self):
        """Verificar stop-loss e take-profit para margin"""
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
            self.execute_margin_trade(signal)
        
        # Stop-loss
        elif pnl_pct <= -self.stop_loss * 100:
            logger.info(f"🛑 STOP-LOSS ATINGIDO: {pnl_pct:.2f}%")
            signal = 'CLOSE_LONG' if self.position_side == 'long' else 'CLOSE_SHORT'
            self.execute_margin_trade(signal)
    
    def run(self):
        """Loop principal MARGIN"""
        logger.info("⚡ INICIANDO MARGIN TRADING")
        
        trade_count = 0
        max_trades_per_day = 8  # Mais trades com margin
        
        while True:
            try:
                # Verificar SL/TP primeiro
                self.check_margin_limits()
                
                # Obter dados
                df = self.get_market_data()
                
                if df is not None:
                    # Gerar sinal
                    signal = self.generate_margin_signal(df)
                    
                    if signal:
                        logger.info(f"📡 SINAL MARGIN: {signal}")
                        
                        # Executar trade
                        if self.execute_margin_trade(signal):
                            trade_count += 1
                            logger.info(f"🎯 TRADES HOJE: {trade_count}/{max_trades_per_day}")
                            
                            if trade_count >= max_trades_per_day:
                                logger.info("⏸️  LIMITE DIÁRIO ATINGIDO. Aguardando...")
                                time.sleep(3600)
                    
                    # Status atual
                    balance = self.exchange.fetch_balance()
                    free_usdt = balance['USDT']['free'] if 'USDT' in balance else 0
                    
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    
                    logger.info(f"📊 MARGIN STATUS: ${free_usdt:.2f} USDT livre")
                    logger.info(f"📈 SOL: ${ticker['last']:.2f} ({ticker['percentage']:.2f}%)")
                    
                    if self.in_position:
                        current_price = ticker['last']
                        if self.position_side == 'long':
                            current_pnl = (current_price - self.entry_price) / self.entry_price * 100
                        else:
                            current_pnl = (self.entry_price - current_price) / self.entry_price * 100
                        
                        logger.info(f"💰 POSIÇÃO: {self.position_side.upper()} {self.position_amount} SOL")
                        logger.info(f"   PnL atual: {current_pnl:+.2f}%")
                    
                    logger.info(f"💰 PnL TOTAL: ${self.total_pnl:.4f}")
                    logger.info("-" * 40)
                
                # Aguardar 3 minutos
                time.sleep(180)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot interrompido")
                break
            except Exception as e:
                logger.error(f"❌ Erro: {e}")
                time.sleep(30)

if __name__ == "__main__":
    # Iniciar com 3x alavancagem
    bot = MarginTradingBot(leverage=3)
    bot.run()