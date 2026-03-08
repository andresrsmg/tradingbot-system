#!/usr/bin/env python3
"""
CRYPTO TRADING BOT - SOLANA (SOL/USDT)
Bot ultra-rápido para trading automatizado em futures de Solana
"""

import ccxt
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional
import json

# Configuração
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SolanaTradingBot:
    """Bot de trading para Solana Futures"""
    
    def __init__(self, exchange_name='binance', testnet=True):
        self.exchange_name = exchange_name
        self.testnet = testnet
        self.exchange = None
        self.symbol = 'SOL/USDT:USDT'  # Perpétuo SOL/USDT
        self.position = None  # None, 'long', 'short'
        self.entry_price = 0
        self.position_size = 0
        
        # Parâmetros de risco
        self.stop_loss_pct = 0.02  # 2%
        self.take_profit_pct = 0.04  # 4%
        self.max_position_size = 0.1  # 10% do capital por trade
        
        # Inicializar exchange
        self._init_exchange()
        
        logger.info(f"Bot Solana inicializado: {exchange_name} {'Testnet' if testnet else 'Mainnet'}")
    
    def _init_exchange(self):
        """Inicializar conexão com exchange"""
        try:
            if self.exchange_name == 'binance':
                self.exchange = ccxt.binance({
                    'apiKey': 'YOUR_API_KEY',
                    'secret': 'YOUR_SECRET_KEY',
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'future',
                    }
                })
                
                if self.testnet:
                    self.exchange.set_sandbox_mode(True)
                    logger.info("Modo Testnet ativado")
            
            elif self.exchange_name == 'bybit':
                self.exchange = ccxt.bybit({
                    'apiKey': 'YOUR_API_KEY',
                    'secret': 'YOUR_SECRET_KEY',
                    'enableRateLimit': True,
                })
            
            elif self.exchange_name == 'okx':
                self.exchange = ccxt.okx({
                    'apiKey': 'YOUR_API_KEY',
                    'secret': 'YOUR_SECRET_KEY',
                    'enableRateLimit': True,
                })
            
            # Carregar mercados
            self.exchange.load_markets()
            logger.info(f"Exchange {self.exchange_name} conectada")
            
        except Exception as e:
            logger.error(f"Erro ao conectar com exchange: {e}")
            raise
    
    def get_account_balance(self) -> Dict:
        """Obter saldo da conta"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            sol_balance = balance.get('SOL', {}).get('free', 0)
            
            return {
                'USDT': float(usdt_balance),
                'SOL': float(sol_balance),
                'total': float(usdt_balance) + float(sol_balance)
            }
        except Exception as e:
            logger.error(f"Erro ao obter saldo: {e}")
            return {'USDT': 0, 'SOL': 0, 'total': 0}
    
    def get_market_data(self, timeframe='5m', limit=50) -> Optional[pd.DataFrame]:
        """Obter dados de mercado recentes"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol, 
                timeframe=timeframe, 
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
        except Exception as e:
            logger.error(f"Erro ao obter dados: {e}")
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calcular indicadores técnicos"""
        try:
            # Médias móveis
            df['sma_10'] = df['close'].rolling(window=10).mean()
            df['sma_30'] = df['close'].rolling(window=30).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Volume médio
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            
            # Últimos valores
            last = df.iloc[-1]
            
            return {
                'price': float(last['close']),
                'sma_10': float(last['sma_10']),
                'sma_30': float(last['sma_30']),
                'rsi': float(last['rsi']),
                'volume_ratio': float(last['volume'] / last['volume_sma']),
                'trend': 'bullish' if last['sma_10'] > last['sma_30'] else 'bearish'
            }
        except Exception as e:
            logger.error(f"Erro ao calcular indicadores: {e}")
            return None
    
    def generate_signal(self, indicators: Dict) -> str:
        """Gerar sinal de trading baseado em indicadores"""
        if not indicators:
            return 'hold'
        
        price = indicators['price']
        sma_10 = indicators['sma_10']
        sma_30 = indicators['sma_30']
        rsi = indicators['rsi']
        volume_ratio = indicators['volume_ratio']
        
        # Estratégia: Trend following com confirmação de volume
        buy_conditions = [
            sma_10 > sma_30,  # Trend bullish
            rsi < 70,  # Não sobrecomprado
            volume_ratio > 1.2,  # Volume acima da média
            price > sma_10  # Preço acima da média rápida
        ]
        
        sell_conditions = [
            sma_10 < sma_30,  # Trend bearish
            rsi > 30,  # Não sobrevendido
            volume_ratio > 1.2,  # Volume acima da média
            price < sma_10  # Preço abaixo da média rápida
        ]
        
        if all(buy_conditions):
            return 'buy'
        elif all(sell_conditions):
            return 'sell'
        
        return 'hold'
    
    def calculate_position_size(self, balance: float, price: float) -> float:
        """Calcular tamanho da posição baseado no capital"""
        risk_capital = balance * self.max_position_size
        position_size = risk_capital / price
        
        # Arredondar para quantidade mínima da exchange
        market = self.exchange.market(self.symbol)
        min_amount = market['limits']['amount']['min']
        
        position_size = max(position_size, min_amount)
        position_size = round(position_size / min_amount) * min_amount
        
        return position_size
    
    def place_order(self, side: str, amount: float, price: float = None):
        """Colocar ordem na exchange"""
        try:
            order_type = 'market' if price is None else 'limit'
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price
            )
            
            logger.info(f"Ordem {side.upper()} executada: {amount} SOL @ ${price or 'market'}")
            logger.info(f"Order ID: {order['id']}")
            
            return order
        except Exception as e:
            logger.error(f"Erro ao colocar ordem: {e}")
            return None
    
    def check_stop_loss_take_profit(self, current_price: float):
        """Verificar stop-loss e take-profit"""
        if self.position is None:
            return False
        
        if self.position == 'long':
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            if pnl_pct <= -self.stop_loss_pct:
                logger.warning(f"STOP-LOSS acionado: {pnl_pct*100:.2f}%")
                self.close_position(current_price)
                return True
            elif pnl_pct >= self.take_profit_pct:
                logger.info(f"TAKE-PROFIT acionado: {pnl_pct*100:.2f}%")
                self.close_position(current_price)
                return True
        
        elif self.position == 'short':
            pnl_pct = (self.entry_price - current_price) / self.entry_price
            
            if pnl_pct <= -self.stop_loss_pct:
                logger.warning(f"STOP-LOSS acionado: {pnl_pct*100:.2f}%")
                self.close_position(current_price)
                return True
            elif pnl_pct >= self.take_profit_pct:
                logger.info(f"TAKE-PROFIT acionado: {pnl_pct*100:.2f}%")
                self.close_position(current_price)
                return True
        
        return False
    
    def close_position(self, price: float = None):
        """Fechar posição atual"""
        if self.position is None:
            return
        
        side = 'sell' if self.position == 'long' else 'buy'
        self.place_order(side, self.position_size, price)
        
        # Calcular PnL
        if self.position == 'long':
            pnl_pct = (price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - price) / self.entry_price
        
        logger.info(f"Posição {self.position} fechada. PnL: {pnl_pct*100:.2f}%")
        
        # Resetar posição
        self.position = None
        self.entry_price = 0
        self.position_size = 0
    
    def execute_strategy(self):
        """Executar ciclo completo da estratégia"""
        try:
            # 1. Obter dados de mercado
            df = self.get_market_data(timeframe='5m', limit=100)
            if df is None or len(df) < 50:
                logger.warning("Dados insuficientes")
                return
            
            # 2. Calcular indicadores
            indicators = self.calculate_indicators(df)
            if indicators is None:
                return
            
            current_price = indicators['price']
            
            # 3. Verificar stop-loss/take-profit
            if self.check_stop_loss_take_profit(current_price):
                return
            
            # 4. Gerar sinal
            signal = self.generate_signal(indicators)
            
            # 5. Obter saldo
            balance_info = self.get_account_balance()
            available_balance = balance_info['USDT']
            
            # 6. Executar baseado no sinal
            if signal == 'buy' and self.position != 'long':
                # Fechar short se existir
                if self.position == 'short':
                    self.close_position(current_price)
                
                # Calcular tamanho da posição
                position_size = self.calculate_position_size(available_balance, current_price)
                
                # Colocar ordem
                order = self.place_order('buy', position_size)
                if order:
                    self.position = 'long'
                    self.entry_price = current_price
                    self.position_size = position_size
            
            elif signal == 'sell' and self.position != 'short':
                # Fechar long se existir
                if self.position == 'long':
                    self.close_position(current_price)
                
                # Calcular tamanho da posição
                position_size = self.calculate_position_size(available_balance, current_price)
                
                # Colocar ordem
                order = self.place_order('sell', position_size)
                if order:
                    self.position = 'short'
                    self.entry_price = current_price
                    self.position_size = position_size
            
            # Log do status
            self.log_status(indicators, balance_info, signal)
            
        except Exception as e:
            logger.error(f"Erro na execução da estratégia: {e}")
    
    def log_status(self, indicators: Dict, balance: Dict, signal: str):
        """Logar status atual"""
        status = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'price': f"${indicators['price']:.2f}",
            'position': self.position or 'None',
            'entry_price': f"${self.entry_price:.2f}" if self.entry_price else 'N/A',
            'signal': signal,
            'balance_usdt': f"${balance['USDT']:.2f}",
            'balance_sol': f"{balance['SOL']:.4f} SOL",
            'rsi': f"{indicators['rsi']:.1f}",
            'trend': indicators['trend']
        }
        
        logger.info(f"Status: {json.dumps(status, indent=2)}")
    
    def run(self, duration_hours=24, check_interval_seconds=60):
        """Executar bot continuamente"""
        logger.info(f"Iniciando trading bot por {duration_hours} horas")
        logger.info(f"Par: {self.symbol}")
        logger.info(f"Check interval: {check_interval_seconds}s")
        
        start_time = time.time()
        cycle_count = 0
        
        try:
            while time.time() - start_time < duration_hours * 3600:
                cycle_count += 1
                logger.info(f"\n{'='*50}")
                logger.info(f"Ciclo #{cycle_count}")
                logger.info(f"{'='*50}")
                
                # Executar estratégia
                self.execute_strategy()
                
                # Aguardar próximo ciclo
                logger.info(f"Aguardando {check_interval_seconds} segundos...")
                time.sleep(check_interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Bot interrompido pelo usuário")
        except Exception as e:
            logger.error(f"Erro fatal: {e}")
        finally:
            # Fechar posição aberta se existir
            if self.position is not None:
                try:
                    df = self.get_market_data(limit=1)
                    if df is not None:
                        current_price = float(df.iloc[-1]['close'])
                        self.close_position(current_price)
                except:
                    pass
            
            logger.info("Bot finalizado")
            logger.info(f"Total de ciclos: {cycle_count}")

def main():
    """Função principal"""
    print("=" * 60)
    print("🚀 CRYPTO TRADING BOT - SOLANA (SOL/USDT)")
    print("=" * 60)
    
    print("\n⚠️  CONFIGURAÇÃO NECESSÁRIA:")
    print("1. Crie conta na Binance/Bybit/OKX")
    print("2. Ative API Trading com permissões necessárias")
    print("3. Configure API Key e Secret no código")
    print("4. Use TESTNET primeiro para validação!")
    
    print("\n📋 CONFIGURAÇÃO RÁPIDA:")
    
    # Selecionar exchange
    exchange = input("Exchange (binance/bybit/okx) [binance]: ").strip().lower() or "binance"
    
    # Modo testnet
    testnet_input = input("Usar Testnet? (s/n) [s]: ").strip().lower() or "s"
    testnet = testnet_input == "s"
    
    # Duração
    duration = int(input("Duração em horas [24]: ").strip() or "24")
    
    print("\n" + "=" * 60)
    print("INICIANDO BOT...")
    print("=" * 60)
    
    # Inicializar bot
    bot = SolanaTradingBot(exchange_name=exchange, testnet=testnet)
    
    # Executar
    bot.run(duration_hours=duration, check_interval_seconds=60)

if __name__ == "__main__":
    main()