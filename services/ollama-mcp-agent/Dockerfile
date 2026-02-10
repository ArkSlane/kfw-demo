FROM node:20-slim

WORKDIR /app

COPY services/ollama-mcp-agent/package.json ./package.json
RUN npm install --omit=dev

COPY services/ollama-mcp-agent/server.js ./server.js

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
