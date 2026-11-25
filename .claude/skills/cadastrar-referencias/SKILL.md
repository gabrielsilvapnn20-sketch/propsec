---
name: cadastrar-referencias
description: Cadastrar no PropSec os perfis de referência (parcerias fechadas e perfis que vocês gostaram) a partir de prints ou de uma lista de @, e completar os dados visitando cada perfil. Use quando o usuário mandar prints/perfis que já fecharam ou que têm potencial, ou pedir para completar as referências.
---

# Cadastrar referências

As referências ensinam o sistema o que é um perfil bom e viram ponto de partida para
buscar perfis parecidos. Dois tipos:
- `fechado` — já fecharam parceria.
- `gostamos` — perfil bom (stories do jeito que vocês gostam), mesmo que não tenha
  aceitado ou respondido. **Recusa não significa perfil ruim.**

## 1. Ler os prints

Os prints podem estar em `referencias/prints/` ou colados na conversa. Leia cada imagem e
extraia o que estiver visível:
- @ do perfil (obrigatório), nome, seguidores, cidade;
- **views de stories** (print de insights/visualizações que ela mandou) → `story_views_real`.
  Se houver vários stories, use a mediana;
- qualquer anotação do usuário (fechou, recusou, valor).

Se não der para saber se é `fechado` ou `gostamos`, ou o status (fechou / recusou /
sem resposta / ainda não contatada), **pergunte ao usuário uma vez, em lote**, antes de salvar.
Mostre uma tabela do que você leu para ele conferir.

```bash
python propsec.py salvar - --referencia fechado --status fechado <<'JSON'
[{"username": "fulana", "story_views_real": 1450, "observacoes": "print de 12/10"}]
JSON
```
Para `gostamos`, use `--referencia gostamos` e o status certo (`recusou`, `sem_resposta`
ou `aprovado` se ainda não foi contatada).

## 2. Completar os dados no Instagram

Siga as **Regras de segurança** e **Navegar como uma pessoa** da skill `prospectar`
(inclusive `python propsec.py liberar @perfil` antes de abrir cada uma).
Para cada referência, siga o passo **3. Coleta completa** da skill `prospectar`
(mesmos campos, mesmo ritmo, só leitura) e salve com `origem: "referencia"`.
Ao final:

```bash
python propsec.py recalibrar --simular
```

Explique ao usuário, em linguagem simples, o que as referências têm em comum
(faixa de seguidores, views dos reels ÷ seguidores, tipo de conteúdo, cidades, públicos)
e o que isso muda na busca. Se ele concordar, rode `python propsec.py recalibrar`.

Depois sugira rodar a prospecção começando pelas fontes `similar` dessas referências.
