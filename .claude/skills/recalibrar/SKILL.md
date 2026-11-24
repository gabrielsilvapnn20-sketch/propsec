---
name: recalibrar
description: Revisar os resultados da operação (respostas, fechamentos, views reais dos stories) e reajustar a nota dos perfis no PropSec. Use quando o usuário pedir para o sistema aprender, recalibrar, ou quiser um relatório de desempenho.
---

# Recalibrar e relatar

1. `python propsec.py recalibrar --simular` — mostra correlações e pesos sugeridos sem aplicar.
2. `python propsec.py resumo`.
3. Explique em linguagem simples:
   - quais sinais estão prevendo melhor os perfis bons (correlação alta) e quais não;
   - se a estimativa de stories está acertando (taxa antes/depois);
   - taxa de resposta e de fechamento por fonte e por cidade (veja a página
     http://localhost:8000/aprendizado ou consulte o banco `dados/propsec.db` com sqlite);
   - quais fontes merecem mais exploração e quais podem ser desativadas
     (`UPDATE fontes SET ativa=0 WHERE tipo=? AND valor=?`).
4. Se houver pelo menos ~6 perfis com resultado e o usuário concordar, rode
   `python propsec.py recalibrar` (faz backup automático do banco antes).

Lembre o usuário: o dado que mais ensina o sistema é **a views real dos stories** que a
influenciadora informa; registrar isso no perfil (campo "Views reais nos stories") ou com
`python propsec.py status @x fechado --views 1500`.
