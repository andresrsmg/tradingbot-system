#!/usr/bin/env python3
"""
Trading Bot Ultra-Rápido - MVP em Horas
Estratégia: Momentum Breakout 5min em Futuros
"""

import time
import logging
from datetime import datetime
import pandas as pd
import numpy as np

# Configuração básica
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UltraFastTradingBot:
    """Bot de trading para implementação imediata"""
    
    def __init__(self, symbol="ES", initial_capital=100):
        self.symbol = symbol  # S&P 500 E-mini futures
        self.capital = initial_capital
        self.position = None  # None, "LONG", "SHORT"
        self.entry_price = 0
        self.stop_loss_pct = 0.005  # 0.5%
        self.take_profit_pct = 0.01  # 1%
        
        logger.info(f"Bot inicializado: {symbol}, Capital: ${initial_capital}")
    
    def fetch_market_data(self):
        """Simulação de dados de mercado (substituir por API real)"""
        # Em produção: conectar à API do broker
        current_price = 5100.50 + np.random.normal(0, 2)  # Simulação
        volume = np.random.randint(1000, 5000)
        
        return {
            'timestamp': datetime.now(),
            'price': current_price,
            'volume': volume
        }
    
    def calculate_indicators(self, data_points):
        """Cálculo rápido de indicadores de momentum"""
        if len(data_points) < 10:
            return None
        
        prices = [d['price'] for d in data_points[-10:]]
        
        # Média móvel simples de 5 períodos
        sma_5 = np.mean(prices[-5:])
        
        # Média móvel simples de 10 períodos  
        sma_10 = np.mean(prices)
        
        # Momentum (último preço vs 5 períodos atrás)
        momentum = prices[-1] - prices[-6]
        
        return {
            'sma_5': sma_5,
            'sma_10': sma_10,
            'momentum': momentum,
            'current_price': prices[-1]
        }
    
    def generate_signal(self, indicators):
        """Geração de sinal de trading"""
        if indicators is None:
            return "HOLD"
        
        # Estratégia simples: crossover de médias + momentum
        if indicators['sma_5'] > indicators['sma_10'] and indicators['momentum'] > 0:
            return "BUY"
        elif indicators['sma_5'] < indicators['sma_10'] and indicators['momentum'] < 0:
            return "SELL"
        
        return "HOLD"
    
    def execute_trade(self, signal, current_price):
        """Execução simulada de trade"""
        if self.position is None:
            if signal == "BUY":
                self.position = "LONG"
                self.entry_price = current_price
                logger.info(f"ENTRADA LONG @ ${current_price:.2f}")
                return True
            elif signal == "SELL":
                self.position = "SHORT"
                self.entry_price = current_price
                logger.info(f"ENTRADA SHORT @ ${current_price:.2f}")
                return True
        
        # Verificar stop-loss / take-profit
        elif self.position == "LONG":
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            if pnl_pct <= -self.stop_loss_pct:
                logger.info(f"STOP-LOSS LONG @ ${current_price:.2f} (PnL: {pnl_pct*100:.2f}%)")
                self.position = None
            elif pnl_pct >= self.take_profit_pct:
                logger.info(f"TAKE-PROFIT LONG @ ${current_price:.2f} (PnL: {pnl_pct*100:.2f}%)")
                self.position = None
        
        elif self.position == "SHORT":
            pnl_pct = (self.entry_price - current_price) / self.entry_price
            if pnl_pct <= -self.stop_loss_pct:
                logger.info(f"STOP-LOSS SHORT @ ${current_price:.2f} (PnL: {pnl_pct*100:.2f}%)")
                self.position = None
            elif pnl_pct >= self.take_profit_pct:
                logger.info(f"TAKE-PROFIT SHORT @ ${current_price:.2f} (PnL: {pnl_pct*100:.2f}%)")
                self.position = None
        
        return False
    
    def run(self, duration_minutes=60):
        """Loop principal de trading"""
        logger.info(f"Iniciando trading por {duration_minutes} minutos")
        
        data_buffer = []
        start_time = time.time()
        
        while time.time() - start_time < duration_minutes * 60:
            try:
                # 1. Coletar dados
                market_data = self.fetch_market_data()
                data_buffer.append(market_data)
                
                # Manter buffer limitado
                if len(data_buffer) > 20:
                    data_buffer = data_buffer[-20:]
                
                # 2. Calcular indicadores
                indicators = self.calculate_indicators(data_buffer)
                
                if indicators:
                    # 3. Gerar sinal
                    signal = self.generate_signal(indicators)
                    
                    # 4. Executar trade
                    trade_executed = self.execute_trade(signal, indicators['current_price'])
                    
                    # Log do status
                    status = {
                        'time': market_data['timestamp'].strftime('%H:%M:%S'),
                        'price': market_data['price'],
                        'signal': signal,
                        'position': self.position,
                        'entry': self.entry_price if self.position else 'N/A'
                    }
                    logger.info(f"Status: {status}")
                
                # Intervalo de 30 segundos entre ciclos
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Erro no ciclo: {e}")
                time.sleep(5)
        
        logger.info("Trading session concluída")
        logger.info(f"Posição final: {self.position}")
        logger.info(f"Preço de entrada: ${self.entry_price if self.position else 'N/A'}")

def main():
    """Função principal"""
    print("=" * 50)
    print("TRADING BOT ULTRA-RÁPIDO - MVP EM HORAS")
    print("=" * 50)
    
    # Configuração rápida
    symbol = input("Símbolo (padrão ES): ").strip() or "ES"
    capital = float(input("Capital inicial (padrão 100): ").strip() or "100")
    duration = int(input("Duração em minutos (padrão 60): ").strip() or "60")
    
    # Inicializar bot
    bot = UltraFastTradingBot(symbol=symbol, initial_capital=capital)
    
    # Executar
    bot.run(duration_minutes=duration)
    
    print("\n" + "=" * 50)
    print("PRÓXIMOS PASSOS:")
    print("1. Conectar API real do broker")
    print("2. Implementar backtesting com dados históricos")
    print("3. Adicionar múltiplas estratégias")
    print("4. Otimizar parâmetros com machine learning")
    print("=" * 50)

if __name__ == "__main__":
    main()