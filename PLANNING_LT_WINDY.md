# Planejamento de Demonstração Técnica: Visualização de Linha de Transmissão (LT) no Windy

Este documento descreve a estratégia para implementar uma demonstração pontual de visualização de linhas de transmissão sobre o mapa do Windy, utilizando o arquivo KML fornecido.

## 1. Objetivo
Demonstrar a capacidade técnica de sobrepor ativos de engenharia (Linhas de Transmissão e Torres) em um mapa meteorológico dinâmico, permitindo a análise geo-espacial de obras em andamento com contexto climático em tempo real.

## 2. Requisitos de Demonstração
- **Isolamento**: O desenvolvimento será feito em um componente/página separado (`LTDemo`), garantindo que não afete o Hub de Projetos atual.
- **Carga de Dados**: Upload e processamento do arquivo `PTE-LT-XGO-CMD.PEXE.PELM.D060.0001.1-0K(6).kml`.
- **Visualização**: 
    - Renderização da linha de transmissão completa (Polylines).
    - Marcadores individuais para cada torre.
    - Tooltips dinâmicos com detalhes técnicos de cada torre ao passar o mouse.
- **Interatividade**: Zoom automático para a área da linha após o carregamento.

## 3. Análise Técnica

### Como faremos?
1. **Frontend (React)**: Criaremos uma página de demonstração acessível via rota `/demo-lt`.
2. **Mapa**: Utilizaremos a **Windy Leaflet API**. Diferente do `iframe` atual, a API JavaScript permite adicionar camadas (Layers) customizadas sobre os dados meteorológicos.
3. **Parser KML**: Utilizaremos uma biblioteca leve (como `togeojson`) ou um parser customizado para extrair as coordenadas e metadados das tags `<Placemark>`, `<LineString>` e `<Point>` do arquivo XML.
4. **Camada de Dados**: Os dados serão convertidos para GeoJSON em tempo de execução para renderização otimizada no Leaflet.

### Limitações
- **Tamanho do Arquivo**: O KML fornecido tem ~330KB e milhares de linhas. O processamento inicial pode levar alguns segundos no browser.
- **API Windy**: O uso da API JavaScript (além do embed) pode exigir uma chave de API para ambientes de produção, mas para demonstração local/pontual podemos usar a versão trial/pública.
- **Precisão**: A precisão visual depende da qualidade das coordenadas no KML e da projeção do mapa do Windy.

## 4. Estratégia de Implementação (Passo a Passo)
1. **Criação da Rota**: Adicionar `/demo-lt` no `App.tsx`.
2. **Componente de Mapa**: Implementar o `WindyLTMap` que inicializa o Leaflet com o Windy.
3. **Lógica de Upload**: Adicionar um botão discreto para "Carregar Dados LT" que lê o arquivo local.
4. **Renderização de Torres**: Mapear cada `<Placemark>` para um marcador com tooltip formatado (Ex: Nome da Torre, Elevação, Tipo de Obra).
5. **Estilização Premium**: Usar as cores da identidade visual do projeto (Copper/Teal) para as linhas e marcadores, mantendo a estética "High-Tech".

## 5. Por que é fácil de remover?
- Toda a lógica residirá em `frontend/src/pages/LTDemo.tsx` e uma única entrada no arquivo de rotas.
- Nenhum esquema de banco de dados será alterado para esta fase de demonstração (os dados serão processados via upload de arquivo em memória).
- Se o cliente não aprovar, basta deletar o arquivo da página e a rota.

---
**Status atual**: Planejamento concluído. Aguardando sinal verde para iniciar a implementação do componente de mapa isolado.
