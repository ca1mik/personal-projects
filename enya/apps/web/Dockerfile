FROM node:20-bookworm-slim

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

WORKDIR /workspace

RUN corepack enable

COPY package.json pnpm-workspace.yaml ./
COPY packages ./packages
COPY apps/web ./apps/web

RUN pnpm install --no-frozen-lockfile
RUN pnpm --dir apps/web build

EXPOSE 3000

CMD ["pnpm", "--dir", "apps/web", "start"]

