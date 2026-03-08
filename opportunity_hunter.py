#!/usr/bin/env python3
"""
Opportunity Hunter - Sistema de análise multi-par
Analisa SOL, BTC, ETH simultaneamente e identifica melhores oportunidades
"""

import ccxt
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('opportunity_hunter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OpportunityHunter:
    def __init__(self):
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
        
        # Pairs config
        self.pairs = {
            'SOL/USDT:USDT': {
                'leverage': 10,
                'timeframe': '5m',
                'allocation': 0.40,  # 40% do capital
                'min_confidence': 0.7,
                'strategy': 'momentum_swing'
            },
            'BTC/USDT:USDT': {
                'leverage': 3,
                'timeframe': '1h',
                'allocation': 0.30,  # 30% do capital
                'min_confidence': 0.8,
                'strategy': 'trend_following'
            },
            'ETH/USDT:USDT': {
                'leverage': 5,
                'timeframe': '15m',
                'allocation': 0.25,  # 25% do capital
                'min_confidence': 0.75,
                'strategy': 'breakout'
            }
        }
        
        # Estado
        self.opportunities = {}
        self.last_analysis = {}
        self.total_capital = 0
        
        logger.info("="*60)
        logger.info("🎯 OPPORTUNITY HUNTER - ANÁLISE MULTI-PAR")
        logger.info("="*60)
        logger.info(f"Pares monitorados: {len(self.pairs)}")
        logger.info("Estratégias por par:")
        for pair, config in self.pairs.items():
            logger.info(f"  {pair}: {config['strategy']} ({config['leverage']}x)")
    
    def analyze_pair(self, pair, config):
        """Analisar um par específico"""
        try:
            # Buscar dados
            ohlcv = self.exchange.fetch_ohlcv(pair, config['timeframe'], limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calcular indicadores baseados na estratégia
            if config['strategy'] == 'momentum_swing':
                confidence, signal = self.analyze_momentum_swing(df, pair)
            elif config['strategy'] == 'trend_following':
                confidence, signal = self.analyze_trend_following(df, pair)
            elif config['strategy'] == 'breakout':
                confidence, signal = self.analyze_breakout(df, pair)
            else:
                confidence, signal = self.analyze_generic(df, pair)
            
            # Obter dados atuais
            ticker = self.exchange.fetch_ticker(pair)
            
            return {
                'pair': pair,
                'price': ticker['last'],
                'change_24h': ticker['percentage'],
                'volume_24h': ticker['quoteVolume'],
                'signal': signal,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat(),
                'config': config
            }
            
        except Exception as e:
            logger.error(f"Erro análise {pair}: {e}")
            return {
                'pair': pair,
                'error': str(e),
                'confidence': 0,
                'signal': 'ERROR'
            }
    
    def analyze_momentum_swing(self, df, pair):
        """Análise Momentum Swing (para SOL)"""
        # RSI
        df['rsi'] = self.calculate_rsi(df['close'], 14)
        
        # MACD
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Condições LONG
        long_conditions = [
            latest['rsi'] > 50 and latest['rsi'] < 70,
            latest['macd'] > latest['macd_signal'],
            latest['volume_ratio'] > 1.2,
            latest['close'] > df['close'].rolling(window=20).mean().iloc[-1]
        ]
        
        # Condições SHORT
        short_conditions = [
            latest['rsi'] < 50 and latest['rsi'] > 30,
            latest['macd'] < latest['macd_signal'],
            latest['volume_ratio'] > 1.2,
            latest['close'] < df['close'].rolling(window=20).mean().iloc[-1]
        ]
        
        confidence_long = sum(long_conditions) / len(long_conditions)
        confidence_short = sum(short_conditions) / len(short_conditions)
        
        if confidence_long > 0.7 and confidence_long > confidence_short:
            return confidence_long, 'LONG'
        elif confidence_short > 0.7 and confidence_short > confidence_long:
            return confidence_short, 'SHORT'
        else:
            return max(confidence_long, confidence_short), 'NEUTRAL'
    
    def analyze_trend_following(self, df, pair):
        """Análise Trend Following (para BTC)"""
        # Médias móveis
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        df['ema200'] = df['close'].ewm(span=200).mean()
        
        # ADX
        df['adx'] = self.calculate_adx(df, 14)
        
        # ATR para volatilidade
        df['atr'] = self.calculate_atr(df, 14)
        
        latest = df.iloc[-1]
        
        # Tendência de longo prazo
        trend_up = latest['ema20'] > latest['ema50'] > latest['ema200']
        trend_down = latest['ema20'] < latest['ema50'] < latest['ema200']
        
        # Força da tendência
        strong_trend = latest['adx'] > 25
        
        if trend_up and strong_trend:
            confidence = min(0.9, latest['adx'] / 50)
            return confidence, 'LONG'
        elif trend_down and strong_trend:
            confidence = min(0.9, latest['adx'] / 50)
            return confidence, 'SHORT'
        else:
            return 0.3, 'NEUTRAL'
    
    def analyze_breakout(self, df, pair):
        """Análise Breakout (para ETH)"""
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Suporte e resistência
        df['resistance'] = df['high'].rolling(window=20).max()
        df['support'] = df['low'].rolling(window=20).min()
        
        latest = df.iloc[-1]
        
        # Breakout para cima
        breakout_up = latest['close'] > latest['bb_upper'] or latest['close'] > latest['resistance']
        
        # Breakout para baixo
        breakout_down = latest['close'] < latest['bb_lower'] or latest['close'] < latest['support']
        
        # Volume confirmando
        volume_confirmation = latest['volume_ratio'] > 1.5
        
        confidence = 0.5
        
        if breakout_up and volume_confirmation:
            confidence = 0.8
            return confidence, 'LONG'
        elif breakout_down and volume_confirmation:
            confidence = 0.8
            return confidence, 'SHORT'
        else:
            return confidence, 'NEUTRAL'
    
    def analyze_generic(self, df, pair):
        """Análise genérica"""
        # RSI básico
        df['rsi'] = self.calculate_rsi(df['close'], 14)
        
        latest = df.iloc[-1]
        
        if latest['rsi'] > 70:
            return 0.6, 'SHORT'
        elif latest['rsi'] < 30:
            return 0.6, 'LONG'
        else:
            return 0.4, 'NEUTRAL'
    
    def calculate_rsi(self, prices, period=14):
        """RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_adx(self, df, period=14):
        """ADX simplificado"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        
        # Simplified ADX
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def calculate_atr(self, df, period=14):
        """ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def analyze_all_pairs(self):
        """Analisar todos os pares em paralelo"""
        logger.info("🔍 ANALISANDO TODOS OS PARES...")
        
        opportunities = {}
        
        with ThreadPoolExecutor(max_workers=len(self.pairs)) as executor:
            futures = {
                executor.submit(self.analyze_pair, pair, config): (pair, config)
                for pair, config in self.pairs.items()
            }
            
            for future in as_completed(futures):
                pair, config = futures[future]
                try:
                    result = future.result()
                    opportunities[pair] = result
                    
                    if 'error' not in result:
                        logger.info(f"📊 {pair}: {result['signal']} (Confiança: {result['confidence']:.2f})")
                    else:
                        logger.error(f"❌ {pair}: {result['error']}")
                        
                except Exception as e:
                    logger.error(f"❌ Erro futuro {pair}: {e}")
                    opportunities[pair] = {
                        'pair': pair,
                        'error': str(e),
                        'confidence': 0,
                        'signal': 'ERROR'
                    }
        
        self.opportunities = opportunities
        self.last_analysis = datetime.now()
        
        return opportunities
    
    def get_best_opportunity(self):
        """Obter melhor oportunidade baseada em confiança"""
        valid_opportunities = [
            opp for opp in self.opportunities.values() 
            if 'error' not in opp and opp['confidence'] > 0.6
        ]
        
        if not valid_opportunities:
            return None
        
        # Ordenar por confiança
        valid_opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        best = valid_opportunities[0]
        
        logger.info(f"🎯 MELHOR OPORTUNIDADE: {best['pair']}")
        logger.info(f"   Sinal: {best['signal']}")
        logger.info(f"   Confiança: {best['confidence']:.2f}")
        logger.info(f"   Preço: ${best['price']:.2f}")
        logger.info(f"   Change 24h: {best['change_24h']:.2f}%")
        
        return best
    
    def update_capital(self):
        """Atualizar capital total"""
        try:
            balance = self.exchange.fetch_balance()
            self.total_capital = balance['USDT']['total'] if 'USDT' in balance else 0
            logger.info(f"💰 CAPITAL TOTAL: ${self.total_capital:.2f}")
        except Exception as e:
            logger.error(f"❌ Erro capital: {e}")
    
    def run(self):
        """Loop principal"""
        logger.info("🎯 INICIANDO OPPORTUNITY HUNTER")
        
        analysis_count = 0
        
        while True:
            try:
                analysis_count += 1
                logger.info(f"📈 ANÁLISE #{analysis_count}")
                logger.info("-" * 40)
                
                # Atualizar capital
                self.update_capital()
                
                # Analisar todos os pares
                opportunities = self.analyze_all_pairs()
                
                # Mostrar resumo
                logger.info("📋 RESUMO DE OPORTUNIDADES:")
                for pair, opp in opportunities.items():
                    if 'error' not in opp:
                        logger.info(f"  {pair}: {opp['signal']} ({opp['confidence']:.2f})")
                
                # Melhor oportunidade
                best = self.get_best_opportunity()
                if best:
                    logger.info(f"🎯 RECOMENDAÇÃO: {best['pair']} - {best['signal']}")
                
                logger.info("=" * 60)
                
                # Aguardar 5 minutos entre análises
                time.sleep(300)
                
            except KeyboardInterrupt:
                logger.info("🛑 Opportunity Hunter interrompido")
                break
            except Exception as e:
                logger.error(f"❌ Erro principal: {e}")
                time.sleep(60)

if __name__ == "__main__":
    hunter = OpportunityHunter()
    hunter.run()