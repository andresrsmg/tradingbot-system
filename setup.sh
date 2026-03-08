#!/bin/bash

# 🛡️⚔️ TradingBot System - Setup Script
# Configuração completa do sistema de trading

set -e  # Exit on error

echo "🛡️⚔️ CONFIGURAÇÃO DO TRADINGBOT SYSTEM"
echo "========================================"

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale Python 3.8+ primeiro."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION detectado"

# Verificar git
if ! command -v git &> /dev/null; then
    echo "❌ Git não encontrado. Instale git primeiro."
    exit 1
fi

echo "✅ Git detectado"

# Criar ambiente virtual
echo "🔧 Criando ambiente virtual..."
python3 -m venv venv

# Ativar ambiente
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Atualizar pip
echo "🔧 Atualizando pip..."
pip install --upgrade pip

# Instalar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt

# Configurar arquivo .env
echo "🔐 Configurando credenciais..."
if [ ! -f .env ]; then
    if [ -f config_template.env ]; then
        cp config_template.env .env
        echo "⚠️  Arquivo .env criado a partir do template."
        echo "⚠️  EDITAR .env com suas credenciais Bybit antes de executar!"
    else
        echo "❌ config_template.env não encontrado"
        exit 1
    fi
else
    echo "✅ Arquivo .env já existe"
fi

# Criar diretórios necessários
echo "📁 Criando estrutura de diretórios..."
mkdir -p logs backups

# Dar permissões de execução
echo "🔧 Configurando permissões..."
chmod +x trading_supervisor.py
chmod +x bot_bybit_futures.py
chmod +x setup.sh

# Verificar configuração
echo "🔍 Verificando configuração..."
if python3 -c "import ccxt, pandas, numpy, psutil; print('✅ Dependências OK')" &> /dev/null; then
    echo "✅ Todas dependências instaladas"
else
    echo "❌ Erro nas dependências"
    exit 1
fi

# Configurar git (se não configurado)
if [ ! -f .git/config ]; then
    echo "🔧 Configurando Git..."
    git init
    git config user.email "trading@system.com"
    git config user.name "TradingBot System"
fi

echo ""
echo "🎉 CONFIGURAÇÃO COMPLETA!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "1. 🔐 Editar arquivo .env com suas credenciais Bybit"
echo "2. 🚀 Executar: python trading_supervisor.py"
echo "3. 📊 Monitorar: tail -f supervisor.log"
echo ""
echo "🛡️⚔️ SISTEMA PRONTO PARA OPERAÇÃO!"
echo "========================================"