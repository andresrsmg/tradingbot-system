#!/usr/bin/env python3
"""
SUPERVISOR DE TRADING - SISTEMA À PROVA DE FALHAS
"""

import subprocess
import time
import logging
import psutil
import signal
import os
import sys
from datetime import datetime
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingSupervisor:
    def __init__(self):
        self.processes = {
            'sol_futures': {
                'command': ['python', 'bot_bybit_futures.py'],
                'pid': None,
                'restarts': 0,
                'max_restarts': 10,
                'health_check_interval': 30,
                'last_health_check': None,
                'memory_limit_mb': 200,
                'cpu_limit_percent': 80
            },
            'btc_futures': {
                'command': ['python', 'bot_btc_futures.py'],
                'pid': None,
                'restarts': 0,
                'max_restarts': 10,
                'health_check_interval': 30,
                'last_health_check': None,
                'memory_limit_mb': 200,
                'cpu_limit_percent': 80
            },
            'eth_futures': {
                'command': ['python', 'bot_eth_futures.py'],
                'pid': None,
                'restarts': 0,
                'max_restarts': 10,
                'health_check_interval': 30,
                'last_health_check': None,
                'memory_limit_mb': 200,
                'cpu_limit_percent': 80
            },
            'opportunity_hunter': {
                'command': ['python', 'opportunity_hunter.py'],
                'pid': None,
                'restarts': 0,
                'max_restarts': 10,
                'health_check_interval': 60,
                'last_health_check': None,
                'memory_limit_mb': 150,
                'cpu_limit_percent': 60
            }
        }
        
        self.state_file = 'supervisor_state.json'
        self.max_total_restarts = 50
        self.total_restarts = 0
        self.start_time = datetime.now()
        
        logger.info("="*80)
        logger.info("🛡️⚔️ SUPERVISOR DE TRADING - SISTEMA À PROVA DE FALHAS")
        logger.info("="*80)
        logger.info(f"Iniciado em: {self.start_time}")
        logger.info(f"Processos monitorados: {len(self.processes)}")
        
        # Carregar estado anterior
        self.load_state()
    
    def load_state(self):
        """Carregar estado anterior do supervisor"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.total_restarts = state.get('total_restarts', 0)
                    logger.info(f"✅ Estado carregado: {self.total_restarts} reinicializações totais")
        except Exception as e:
            logger.warning(f"⚠️  Não foi possível carregar estado: {e}")
    
    def save_state(self):
        """Salvar estado atual do supervisor"""
        try:
            state = {
                'total_restarts': self.total_restarts,
                'timestamp': datetime.now().isoformat(),
                'processes': {}
            }
            
            for name, proc_info in self.processes.items():
                state['processes'][name] = {
                    'restarts': proc_info['restarts'],
                    'pid': proc_info['pid']
                }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar estado: {e}")
    
    def start_process(self, process_name):
        """Iniciar processo com monitoramento"""
        proc_info = self.processes[process_name]
        
        if proc_info['restarts'] >= proc_info['max_restarts']:
            logger.error(f"🚨 {process_name}: LIMITE DE REINÍCIOS ATINGIDO ({proc_info['restarts']}/{proc_info['max_restarts']})")
            return False
        
        try:
            logger.info(f"🚀 Iniciando {process_name}: {' '.join(proc_info['command'])}")
            
            # Iniciar processo
            process = subprocess.Popen(
                proc_info['command'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            proc_info['pid'] = process.pid
            proc_info['process'] = process
            proc_info['start_time'] = datetime.now()
            proc_info['restarts'] += 1
            self.total_restarts += 1
            
            logger.info(f"✅ {process_name}: PID {process.pid} iniciado")
            logger.info(f"   Reinícios: {proc_info['restarts']}/{proc_info['max_restarts']}")
            
            # Salvar estado
            self.save_state()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar {process_name}: {e}")
            return False
    
    def check_process_health(self, process_name):
        """Verificar saúde do processo"""
        proc_info = self.processes[process_name]
        
        if not proc_info['pid']:
            return 'dead'
        
        try:
            # Verificar se processo existe
            process = psutil.Process(proc_info['pid'])
            
            # Verificar status
            status = process.status()
            
            # Verificar uso de memória
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # Verificar uso de CPU
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # Verificar se está responsivo
            if status == psutil.STATUS_ZOMBIE:
                logger.warning(f"⚠️  {process_name}: Processo zumbi detectado")
                return 'zombie'
            
            # Verificar limites
            if memory_mb > proc_info['memory_limit_mb']:
                logger.warning(f"⚠️  {process_name}: Memória alta ({memory_mb:.1f}MB > {proc_info['memory_limit_mb']}MB)")
                return 'high_memory'
            
            if cpu_percent > proc_info['cpu_limit_percent']:
                logger.warning(f"⚠️  {process_name}: CPU alta ({cpu_percent:.1f}% > {proc_info['cpu_limit_percent']}%)")
                return 'high_cpu'
            
            # Verificar se está rodando
            if status in [psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING]:
                return 'healthy'
            else:
                logger.warning(f"⚠️  {process_name}: Status anormal ({status})")
                return 'unhealthy'
                
        except psutil.NoSuchProcess:
            logger.warning(f"⚠️  {process_name}: Processo não encontrado (PID {proc_info['pid']})")
            return 'dead'
        except Exception as e:
            logger.error(f"❌ Erro ao verificar {process_name}: {e}")
            return 'error'
    
    def restart_process(self, process_name, reason='unknown'):
        """Reiniciar processo com logging detalhado"""
        proc_info = self.processes[process_name]
        
        logger.warning(f"🔄 Reiniciando {process_name}: {reason}")
        
        # Parar processo atual
        self.stop_process(process_name)
        
        # Aguardar breve pausa
        time.sleep(2)
        
        # Iniciar novo processo
        success = self.start_process(process_name)
        
        if success:
            logger.info(f"✅ {process_name}: Reiniciado com sucesso")
        else:
            logger.error(f"❌ {process_name}: Falha ao reiniciar")
        
        return success
    
    def stop_process(self, process_name):
        """Parar processo de forma controlada"""
        proc_info = self.processes[process_name]
        
        if proc_info['pid']:
            try:
                logger.info(f"🛑 Parando {process_name} (PID {proc_info['pid']})")
                
                # Tentar parada graciosa
                process = psutil.Process(proc_info['pid'])
                process.terminate()
                
                # Aguardar término
                try:
                    process.wait(timeout=5)
                    logger.info(f"✅ {process_name}: Parado graciosamente")
                except psutil.TimeoutExpired:
                    # Forçar término
                    process.kill()
                    logger.warning(f"⚠️  {process_name}: Forçado a terminar")
                
                proc_info['pid'] = None
                
            except psutil.NoSuchProcess:
                logger.warning(f"⚠️  {process_name}: Já terminado")
            except Exception as e:
                logger.error(f"❌ Erro ao parar {process_name}: {e}")
    
    def monitor_logs(self, process_name):
        """Monitorar logs do processo em tempo real"""
        proc_info = self.processes[process_name]
        
        if not proc_info.get('process'):
            return
        
        process = proc_info['process']
        
        # Ler stdout
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                logger.info(f"[{process_name}] {line}")
        
        # Ler stderr
        for line in iter(process.stderr.readline, ''):
            line = line.strip()
            if line:
                logger.error(f"[{process_name}-ERROR] {line}")
    
    def emergency_protocol(self):
        """Protocolo de emergência - ação drástica"""
        logger.critical("🚨🚨🚨 PROTOCOLO DE EMERGÊNCIA ATIVADO 🚨🚨🚨")
        
        # 1. Parar TODOS os processos
        for process_name in self.processes:
            self.stop_process(process_name)
        
        # 2. Aguardar 10 segundos
        time.sleep(10)
        
        # 3. Iniciar apenas processo crítico
        critical_process = 'sol_futures'
        logger.info(f"🔄 Iniciando apenas processo crítico: {critical_process}")
        
        success = self.start_process(critical_process)
        
        if success:
            logger.info("✅ Sistema crítico reiniciado")
            return True
        else:
            logger.critical("❌ FALHA CRÍTICA: Não foi possível reiniciar sistema")
            return False
    
    def run(self):
        """Loop principal do supervisor"""
        logger.info("🎯 Iniciando monitoramento contínuo")
        
        # Iniciar todos os processos
        for process_name in self.processes:
            self.start_process(process_name)
        
        # Loop de monitoramento
        while True:
            try:
                current_time = datetime.now()
                
                # Verificar cada processo
                for process_name, proc_info in self.processes.items():
                    # Verificar saúde
                    health = self.check_process_health(process_name)
                    
                    # Ações baseadas na saúde
                    if health == 'dead':
                        logger.warning(f"💀 {process_name}: Processo morto detectado")
                        self.restart_process(process_name, reason="processo morto")
                    
                    elif health in ['zombie', 'high_memory', 'high_cpu', 'unhealthy']:
                        logger.warning(f"⚠️  {process_name}: Saúde ruim ({health})")
                        self.restart_process(process_name, reason=f"saúde ruim: {health}")
                    
                    elif health == 'healthy':
                        # Atualizar último check saudável
                        proc_info['last_health_check'] = current_time
                
                # Verificar restarts totais
                if self.total_restarts > self.max_total_restarts:
                    logger.critical(f"🚨 LIMITE TOTAL DE REINÍCIOS ATINGIDO: {self.total_restarts}")
                    if not self.emergency_protocol():
                        logger.critical("💀 SISTEMA IRRECUPERÁVEL - REQUER INTERVENÇÃO HUMANA")
                        break
                
                # Status periódico
                if int(current_time.timestamp()) % 300 == 0:  # A cada 5 minutos
                    logger.info("📊 STATUS DO SISTEMA:")
                    for process_name, proc_info in self.processes.items():
                        status = "✅ ATIVO" if proc_info['pid'] else "❌ INATIVO"
                        logger.info(f"   {process_name}: {status} (PID: {proc_info['pid']}, Restarts: {proc_info['restarts']})")
                    logger.info(f"   Total restarts: {self.total_restarts}/{self.max_total_restarts}")
                    logger.info(f"   Uptime: {current_time - self.start_time}")
                
                # Salvar estado periodicamente
                if int(current_time.timestamp()) % 60 == 0:
                    self.save_state()
                
                # Aguardar próximo check
                time.sleep(10)
                
            except KeyboardInterrupt:
                logger.info("🛑 Supervisor interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro no supervisor: {e}")
                time.sleep(30)
        
        # Parar todos os processos ao sair
        logger.info("🛑 Parando todos os processos...")
        for process_name in self.processes:
            self.stop_process(process_name)
        
        logger.info("👋 Supervisor finalizado")

if __name__ == "__main__":
    supervisor = TradingSupervisor()
    supervisor.run()