# ✈️ Promo Alerts - SP → Recife

Sistema automatizado para monitorar **preços de passagens** e **ofertas de milhas** de São Paulo para Recife.

## 🎯 **Funcionalidades**

- ✅ **Preços em tempo real** via APIs gratuitas
- ✅ **Estimativas de milhas** (Smiles, TudoAzul, LATAM Pass, Livelo)
- ✅ **Análise de ofertas** (EXCELENTE, BOA, REGULAR)
- ✅ **Notificações inteligentes** via Telegram
- ✅ **GitHub Actions** automático (3x/dia)
- ✅ **Histórico de preços** (30 dias)

## 🆓 **APIs Utilizadas (100% Gratuitas)**

### **1. Amadeus Self-Service**
- **Free Tier**: 2.000 requests/mês
- **Dados**: Preços reais GRU/CGH → REC

### **2. OpenSky Network** 
- **Free Tier**: 4.000 créditos/mês
- **Dados**: Tráfego aéreo em tempo real

### **3. Estimativas de Milhas**
- **100% Gratuito**: Algoritmo próprio
- **Programas**: Smiles, TudoAzul, LATAM Pass, Livelo

## 🚀 **Setup Rápido**

### **1. APIs - Cadastrar apenas 1:**
```bash
# Amadeus (OBRIGATÓRIO)
https://developers.amadeus.com/
→ Create account → Create app → Copy API Key + Secret

# OpenSky (JÁ TEM)
✅ Client ID: dieg0x6f-api-client
```

### **2. GitHub Secrets:**
```bash
# Repositório → Settings → Secrets → Actions
AMADEUS_API_KEY=your_test_api_key
AMADEUS_API_SECRET=your_test_api_secret
OPENSKY_CLIENT_ID=dieg0x6f-api-client
OPENSKY_CLIENT_SECRET=  # (vazio se não tiver)

# Opcional (Telegram)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### **3. Executar:**
```bash
# Localmente
cd app/
python flight_price_apis.py

# GitHub Actions
# ✅ Executa automaticamente 3x/dia (8h, 14h, 20h)
# ✅ Ou manualmente via workflow_dispatch
```

## 📊 **Exemplo de Resultado**

```bash
🎯 RESULTADO:
   💰 Preço mais barato: R$ 389.00
   ✈️  Melhor origem: GRU
   🏢 Companhia: G3  
   📊 Avaliação: BOA
   💡 ✅ Boa oferta por R$389. Recomendado!

💳 MELHOR OPÇÃO EM MILHAS:
   🎫 Programa: TudoAzul (Azul)
   ✈️  Milhas necessárias: 22,000
   💰 Taxas: R$ 140
   💡 Vale a pena? SIM

🤖 GitHub Actions Output:
   SP→REC: R$389 (BOA) | Melhor milhas: TudoAzul (22,000 milhas + R$140)
```

## 🔔 **Notificações Automáticas**

### **Critérios para Alerta:**
- Preço classificado como **EXCELENTE** ou **BOA**
- Economia mínima de **R$ 50** vs mercado
- Preço final **abaixo de R$ 500**

### **Exemplo de Notificação:**
```
🔥 OFERTA SP → RECIFE DETECTADA!

💰 Preço: R$ 299.00
📊 Avaliação: EXCELENTE
✈️ Origem: GRU | 🏢 GOL

💳 Melhor milhas: Smiles
✈️ 18,000 milhas + R$ 120
💡 Vale usar milhas? SIM

💡 🔥 COMPRE AGORA! Preço excelente
⏰ Detectado às 14:30 - 15/12/2024
```

## 📈 **Filtros Inteligentes**

### **Foco Absoluto em Recife:**
- Deve mencionar: `recife`, `pernambuco`, ` pe `, ` rec `, `gru-rec`
- E mencionar: `voo`, `passagem`, `aereo`, `voar`
- Ignora posts não relacionados a voos para PE

### **Análise de Preços:**
- Compara promoção vs preços de mercado atuais
- Calcula economia e percentual de desconto
- Avalia se vale usar milhas ou dinheiro

## 🗂️ **Estrutura do Projeto**

```
promo-alerts/
├── app/
│   ├── main.py              # Monitor principal (RSS + APIs)
│   ├── flight_price_apis.py # APIs de preços focadas
│   ├── feeds.yml           # Configuração de feeds RSS
│   └── filters.yml         # Filtros de conteúdo
├── .github/workflows/
│   └── flight-prices.yml   # Automação GitHub Actions
└── data/
    ├── seen.json           # Posts já processados
    └── price_history/      # Histórico de preços (30 dias)
```

## ⚙️ **Configuração dos Filtros**

### **filters.yml:**
```yaml
enabled: true
keywords:
  enabled: true
  miles_keywords:
    - "milhas"
    - "smiles" 
    - "tudoazul"
    - "latam pass"
    - "livelo"
```

### **feeds.yml:**
```yaml
feeds:
  - name: Passageiro de Primeira
    url: https://passageirodeprimeira.com/feed/
  - name: MaxMilhas Blog
    url: https://blog.maxmilhas.com.br/feed/
  # ... mais feeds
```

## 💰 **Custo Total: R$ 0,00/mês**

- ✅ Amadeus: 2.000 requests gratuitos
- ✅ OpenSky: 4.000 créditos gratuitos
- ✅ GitHub Actions: 2.000 min/mês gratuitos
- ✅ Algoritmos próprios: Grátis

## 📊 **Monitoramento**

### **Uso das APIs:**
```json
{
  "api_usage": {
    "amadeus_requests": 2,
    "opensky_requests": 1,
    "remaining_free_requests": {
      "amadeus": "~1998/2000",
      "opensky": "~3999/4000 créditos"
    }
  }
}
```

### **GitHub Actions:**
- **Frequência**: 3x/dia (dias úteis)
- **Horários**: 8h, 14h, 20h (horário brasileiro)
- **Duração**: ~2-3 minutos por execução
- **Notificação**: Apenas para ofertas boas

## 🛠️ **Troubleshooting**

### **Erro: Token Amadeus**
```bash
❌ Erro ao obter token Amadeus
→ Verificar AMADEUS_API_KEY e AMADEUS_API_SECRET
```

### **Erro: OpenSky**
```bash
❌ Erro OpenSky API
→ Verificar OPENSKY_CLIENT_ID (deve ser: dieg0x6f-api-client)
```

### **Sem Posts Encontrados**
```bash
✨ No new posts found
→ Normal - sistema busca apenas posts específicos sobre Recife
```

## 🎯 **Sistema Focado e Eficiente**

- **1 cadastro obrigatório** (Amadeus)
- **APIs confiáveis** e gratuitas
- **Execução automática** via GitHub Actions
- **Notificações inteligentes** apenas para ofertas boas
- **Custo zero** permanente

---

**🚀 Sistema completo para monitorar ofertas SP → Recife com precisão e economia!**