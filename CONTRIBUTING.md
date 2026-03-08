# 🤝 GUIA DE CONTRIBUIÇÃO

## 🎯 VISÃO DO PROJETO

Criar o **sistema de trading mais resiliente do mercado**, com:
- ✅ **Zero downtime** (supervisor à prova de falhas)
- ✅ **Multi-pair trading** simultâneo
- ✅ **Risk management** avançado
- ✅ **Collaborative development** com equipe

## 👥 EQUIPE

### **DESENVOLVEDORES ATIVOS:**
1. **Aquiles** (@) - Arquitetura & Estratégia
2. **Andres** (andresrsmg@gmail.com) - Desenvolvimento & Melhorias
3. **Você** - Operações & Trading

### **PERMISSÕES GITHUB:**
- **Write access**: Push para branches, criar PRs
- **Admin access**: Gerenciamento de repositório
- **Maintainer**: Review e merge de PRs

## 🔄 FLUXO DE TRABALHO

### **1. CLONAR REPOSITÓRIO:**
```bash
git clone https://github.com/[organization]/tradingbot-system.git
cd tradingbot-system
```

### **2. CONFIGURAR AMBIENTE:**
```bash
# Instalar dependências
./setup.sh

# Configurar credenciais (criar .env)
cp config_template.env .env
# Editar .env com suas credenciais
```

### **3. BRANCH STRATEGY:**
```
main
├── develop
│   ├── feature/nova-estrategia
│   ├── feature/dashboard-web
│   └── bugfix/corrige-timeout
└── hotfix/critical-bug
```

### **4. CRIAR NOVA FEATURE:**
```bash
# Criar branch a partir de develop
git checkout develop
git pull origin develop
git checkout -b feature/nome-da-feature

# Desenvolver
# ... código ...

# Testar localmente
python trading_supervisor.py
# Verificar logs

# Commit
git add .
git commit -m "feat: adiciona [feature] para [objetivo]"

# Push
git push origin feature/nome-da-feature
```

### **5. CRIAR PULL REQUEST:**
1. Acessar GitHub → Pull Requests → New
2. **Base**: `develop` (NUNCA merge direto em `main`)
3. **Compare**: `feature/nome-da-feature`
4. **Title**: `[FEAT] Nome da feature`
5. **Description**: Detalhar mudanças e testes
6. **Reviewers**: Marcar @andresrsmg e outros
7. **Labels**: `feature`, `enhancement`, etc.

## 📝 CONVENÇÕES DE CÓDIGO

### **ESTRUTURA DE ARQUIVOS:**
```
tradingbot-system/
├── src/                    # Código fonte
│   ├── bots/              # Bots de trading
│   ├── strategies/        # Estratégias
│   ├── risk/              # Gestão de risco
│   └── utils/             # Utilitários
├── tests/                 # Testes
├── docs/                  # Documentação
└── scripts/               # Scripts auxiliares
```

### **CONVENÇÕES DE COMMIT:**
```
feat:     Nova feature
fix:      Correção de bug
docs:     Documentação
style:    Formatação (não afeta código)
refactor: Refatoração
test:     Testes
chore:    Tarefas de manutenção
```

**Exemplos:**
- `feat: adiciona bot ETH/USDT com estratégia breakout`
- `fix: corrige memory leak no supervisor`
- `docs: atualiza README com instruções de deploy`

### **CONVENÇÕES DE NOMENCLATURA:**
- **Classes**: `CamelCase` (`TradingSupervisor`)
- **Funções**: `snake_case` (`calculate_rsi`)
- **Variáveis**: `snake_case` (`position_size`)
- **Constantes**: `UPPER_SNAKE_CASE` (`MAX_RESTARTS`)

## 🧪 TESTES

### **TESTES OBRIGATÓRIOS:**
1. **Unit tests**: Funções individuais
2. **Integration tests**: Módulos integrados
3. **System tests**: Sistema completo
4. **Performance tests**: CPU/memória

### **EXECUTAR TESTES:**
```bash
# Todos os testes
pytest tests/

# Testes específicos
pytest tests/test_supervisor.py -v

# Com coverage
pytest --cov=src tests/
```

### **COVERAGE MÍNIMO:**
- **Código novo**: 80%+ coverage
- **Código crítico**: 90%+ coverage
- **Supervisor**: 95%+ coverage

## 🔒 SEGURANÇA

### **NUNCA COMMITAR:**
- ✅ Credenciais API (.env, keys)
- ✅ Chaves privadas
- ✅ Configurações sensíveis
- ✅ Logs com dados pessoais

### **ARQUIVOS SENSÍVEIS:**
```
# .gitignore deve incluir:
.env
*.key
*.pem
*.secret
*.log (com dados sensíveis)
supervisor_state.json
```

### **REVIEW DE SEGURANÇA:**
1. **Todos os PRs** passam por review de segurança
2. **Credenciais**: Nunca hardcoded, sempre .env
3. **API keys**: Rotação periódica recomendada
4. **Logs**: Sem dados sensíveis em logs públicos

## 📊 CODE REVIEW

### **CHECKLIST DE REVIEW:**
- [ ] Código segue convenções
- [ ] Testes passam
- [ ] Coverage adequado
- [ ] Documentação atualizada
- [ ] Sem credenciais hardcoded
- [ ] Performance aceitável
- [ ] Segurança verificada

### **PROCESSO DE REVIEW:**
1. **Autor** cria PR
2. **Reviewer** analisa em 24h
3. **Comentários** são adicionados
4. **Autor** corrige se necessário
5. **Approval** de pelo menos 1 reviewer
6. **Merge** para develop

## 🚀 DEPLOY

### **AMBIENTES:**
- **Development**: `develop` branch (testes)
- **Staging**: Pré-produção (validação)
- **Production**: `main` branch (estável)

### **PROCESSO DE DEPLOY:**
```bash
# 1. Merge develop -> main (após testes)
git checkout main
git merge develop --no-ff -m "release: v1.2.0"

# 2. Tag version
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin main --tags

# 3. Deploy em produção
# (processo automatizado ou manual)
```

## 📞 COMUNICAÇÃO

### **CANAL PRINCIPAL:**
- **GitHub Issues**: Bugs e features
- **GitHub Discussions**: Ideias e planejamento
- **Email**: andresrsmg@gmail.com (urgências)

### **REUNIÕES:**
- **Weekly sync**: Segunda-feira 10:00 UTC
- **Planning**: Início de sprint
- **Retrospective**: Fim de sprint

## 🎯 METAS DE QUALIDADE

### **KPIs DO PROJETO:**
- **Uptime**: 99.9% (supervisor)
- **Performance**: < 200ms por análise
- **Reliability**: 0 falhas críticas/mês
- **Security**: 0 vulnerabilidades conhecidas

### **METAS DE EQUIPE:**
- **Velocity**: 5-10 PRs/semana
- **Quality**: < 5% bug rate
- **Collaboration**: 100% PRs com review

---

**🤝 JUNTOS CONSTRUÍMOS O MELHOR SISTEMA DE TRADING!** 🚀

*Última atualização: 2026-03-08 por Aquiles*