FROM node:20-slim

WORKDIR /app

COPY services/playwright-mcp-agent/package.json ./
RUN npm install --omit=dev

COPY services/playwright-mcp-agent/server.js ./

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
