# ---- build ----
FROM node:22-bookworm-slim AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.28.0 --activate
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc tsconfig.base.json ./
COPY packages/shared/package.json packages/shared/
COPY apps/api/package.json apps/api/
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile
COPY packages packages
COPY apps apps
RUN pnpm --filter @ws/web build && pnpm --filter @ws/api build
RUN pnpm deploy --filter @ws/api --prod --legacy /out/api && cp -r apps/api/dist apps/api/migrations /out/api/ && mkdir -p /out/web && cp -r apps/web/dist /out/web/dist

# ---- runtime ----
FROM node:22-bookworm-slim
ENV NODE_ENV=production PORT=3000 HOST=0.0.0.0 SERVE_WEB=true
WORKDIR /srv/app/apps/api
COPY --from=build /out/api /srv/app/apps/api
COPY --from=build /out/web /srv/app/apps/web
# Run as the unprivileged "node" user; the app never needs root.
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD node -e "fetch('http://127.0.0.1:3000/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "dist/server.js"]
