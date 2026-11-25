---
name: prospectar
description: Rodar uma sessão de prospecção de influenciadoras no Instagram pelo Claude in Chrome — encontrar perfis seguindo as sugestões a partir de perfis bons, analisar e salvar no PropSec. Use quando o usuário pedir para prospectar, buscar perfis, achar influenciadoras ou rodar o agente.
---

# Sessão de prospecção

Você navega no Instagram com a conta de prospecção (já logada no Chrome) e salva perfis no
PropSec. **Só leitura:** nunca envie mensagem, siga, curta, comente, reaja ou responda story.
Antes de usar o navegador, carregue a skill `anthropic-skills:chrome-browser`.
Trabalhe numa aba nova do Chrome; não mexa nas outras abas.

## Regras de segurança (obrigatórias)

1. **Antes de abrir CADA perfil**, rode o porteiro com timeout de 10 minutos
   (`timeout: 600000` na ferramenta Bash), porque ele pode esperar alguns minutos:
   ```bash
   python propsec.py liberar @perfil
   ```
   `LIBERADO` → pode abrir. `PARAR: ...` → encerre a sessão (passo 5) e diga o motivo ao
   usuário. Não contorne, não espere por conta própria, não abra "só mais um".
2. Qualquer sinal de alerta do Instagram (login/verificação, captcha, "tente mais tarde",
   "ação bloqueada", "atividade incomum", deslogou, páginas que não carregam) →
   `python propsec.py alerta "o que apareceu"`, encerre e avise o usuário.
3. Se o usuário pediu N perfis, pare em N.

## 1. Abrir a sessão

```bash
python propsec.py sessao inicio
python propsec.py proximas-fontes
```
Se `sessao inicio` disser BLOQUEADO, não comece: diga o motivo.

## 2. Caminho principal: sugestões a partir de perfis bons

O usuário quer **perfis parecidos com os que já deram certo**, achados pelas sugestões do
próprio Instagram. `proximas-fontes` lista as **sementes** (fechadas, aprovadas, referências).

1. Abra uma semente. Ao lado de "Enviar mensagem" há o botão de **perfis semelhantes**
   (ícone de pessoa com "+"). Clique: aparece a faixa de sugestões. Role a faixa para ver mais.
2. Anote os @ das sugestões que parecem mulheres/influenciadoras (pule lojas, páginas,
   homens, famosas grandes).
3. Verifique em lote quais são novos: `python propsec.py existe @a @b @c ...`
   (pule `JA_EXISTE`: já estão no sistema ou já foram contatadas pelo usuário).
4. Analise as novas (passo 3).
5. **Bola de neve:** quando uma nova for boa (nota ≥ 60), use-a como semente também e abra as
   sugestões dela. Assim você sai da rede conhecida.
6. Registre cada semente usada: `python propsec.py fonte sugestoes "<@semente>" --vistos N`.
   Salve os perfis com `"origem": "sugestoes", "origem_detalhe": "<@semente>"`.

**Não use agências** (fly.creators.br, hub.influ.br e parecidas) como fonte: quem elas
seguem já é agenciado. Se um perfil mostrar "Seguido(a) por" uma agência, anote isso nas
observações ("possivelmente agenciada"), mas pode salvar.

**Complemento (no máximo 1/3 da sessão):** cidades e hashtags do bloco 2 de
`proximas-fontes` — principalmente quando as sugestões começarem a repetir perfis já vistos.
Não use páginas de lojas como caminho.

## 3. Analisar um perfil (rápido e objetivo)

Meta: **1 a 2 minutos por perfil**. Prefira ler o texto da página (ferramenta de leitura de
página) em vez de muitas capturas de tela. Não pense demais entre os passos.

**Etapa A — triagem (3 ações no máximo):** `liberar` → abrir o perfil → ler o topo
(seguidores, bio, categoria) e a aba **Reels** (as views aparecem na grade).
Descarte e salve como `ignorado` se:
- menos de 1.000 seguidores; perfil privado; loja, página, homem, empresa; último post há
  mais de 2 meses;
- mais de 20.000 **e** sem cara das referências (acima de 20k só salve se for blogueira/mãe
  com público engajado e stories ativos; escreva "caso especial");
- seguidores claramente comprados (muitos seguidores, views/curtidas ínfimas, comentários de bot).
```bash
echo '{"username":"x","seguidores":42000,"observacoes":"fora da faixa","origem":"sugestoes","origem_detalhe":"semente"}' | python propsec.py salvar - --status ignorado
```

**Etapa B — análise (só para quem passou):** role a página com calma, abra 2–3 posts ou
reels recentes e leia os comentários. Colete:
- `media_views_reels`: **mediana** das views dos 9–12 reels mais recentes (ignore fixados);
- `media_curtidas`, `media_comentarios`: médias dos posts abertos;
- `comentarios_reais` (0 a 1): são pessoas conversando? ela responde?;
- `posts_por_semana`, `stories_ativos` (anel colorido / destaques recentes),
  `faz_publi`, `marca_lojas`, `contato`, `link_bio`, `cidade`, `uf`, `bio`;
- `publicos` (etiquetas livres: mãe, maternidade, mulher de preso, moda, beleza, humor,
  forró, praia, lifestyle, interior...), `tipo_conteudo`, `hashtags`;
- `observacoes`: 1–2 frases dizendo **por que** lembra as referências.

Campo que você não viu: **omita** (não invente, não ponha 0).

```bash
python propsec.py salvar - <<'JSON'
{"username": "maria.blog", "nome": "Maria", "cidade": "Codó", "uf": "MA",
 "seguidores": 6200, "seguindo": 900, "posts": 41,
 "media_views_reels": 4800, "media_curtidas": 380, "media_comentarios": 35,
 "comentarios_reais": 0.8, "stories_ativos": 1, "faz_publi": 1,
 "bio": "...", "publicos": ["mãe", "moda"], "tipo_conteudo": "rotina, provador",
 "observacoes": "...", "origem": "sugestoes", "origem_detalhe": "joicimara"}
JSON
```

**O que as fechadas têm em comum** (`referencias/referencias_iniciais.json`): categoria
"Blogueiro(a)"/"Criador de conteúdo digital", "parcerias no direct", muitas são **mães**,
**poucos posts no feed é normal** (6–31 posts deram resultado), stories ativos, seguem muita
gente, selfies/looks/praia, reels de POV com frase, humor do dia a dia, forró; Nordeste/Norte
e cidades pequenas. Perfis "não tão bons no papel" já deram resultado alto.

## 4. Navegar como uma pessoa

- Chegue nos perfis **clicando** (sugestões, busca), não digitando `instagram.com/usuario`
  em sequência.
- Role aos poucos; não pule direto para o fim. Varie a ordem dos passos.
- De vez em quando (1 a cada 6–8 perfis), volte para o feed ou Explorar por alguns segundos.
- Um perfil por vez, uma aba só. O ritmo entre perfis é do porteiro.

## 5. Encerrar

```bash
python propsec.py fonte sugestoes "<@semente>" --vistos <n>     # para cada semente usada
python propsec.py sessao fim --visitados <total> --salvos <salvos sem ignorados>
python propsec.py resumo
```
Responda ao usuário: quantos perfis viu, quantos bons salvou, os 5 melhores (@, cidade,
seguidores, views médias dos reels, por que vale) e quais sementes renderam mais.
A fila para aprovar fica em http://localhost:8000/fila.
