FROM node:20-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

# Build context is the REPO ROOT, not apps/web (see docker/docker-compose.yml).
# apps/web depends on the `@trace-x/shared` workspace package, so the install
# has to run from the monorepo root against the root lockfile. Installing from
# apps/web alone makes npm resolve @trace-x/shared against the public registry
# and fail the build with:
#   npm error 404  '@trace-x/shared@*' is not in this registry.
# Copy the manifests on their own first so the install layer caches across
# source edits.
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY packages/shared/package.json packages/shared/
RUN npm ci

# The committed root lockfile was generated on Windows, so the only native SWC
# binary it records is @next/swc-win32-x64-msvc. On Linux `npm ci` therefore
# installs no SWC at all and the build falls back to the much slower WASM
# compiler. Install the binary this image needs (alpine => musl, x64).
#
# The version comes from next's own optionalDependencies, not from next's
# version: the two drift apart. next 14.2.35 pins its SWC packages at
# 14.2.33, and @next/swc-linux-x64-musl@14.2.35 does not exist at all, so
# assuming they match fails the build with npm ETARGET.
#
# next is hoisted to the workspace root, with the nested path kept as a
# fallback for a non-hoisted install.
RUN SWC_VERSION="$(node -p "require('next/package.json').optionalDependencies['@next/swc-linux-x64-musl']" 2>/dev/null || node -p "require('./apps/web/node_modules/next/package.json').optionalDependencies['@next/swc-linux-x64-musl']")" && npm install --no-save --ignore-scripts --workspace=apps/web "@next/swc-linux-x64-musl@${SWC_VERSION}"

COPY packages/shared packages/shared
COPY apps/web apps/web

# @trace-x/shared is consumed through its "main"/"types" (dist/), so it must be
# compiled before the web app can import it.
RUN npm run build --workspace=packages/shared --if-present

WORKDIR /app/apps/web

EXPOSE 3000

CMD ["npm", "run", "dev"]
