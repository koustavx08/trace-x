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
# installs no SWC at all, and `next dev` tries to fetch one at runtime -- which
# fails inside a workspace ("npm error code ENOWORKSPACES") and silently drops
# Next.js to its much slower WASM compiler. Install the binary this image
# actually needs (alpine => musl, x64), pinned to the installed next version.
# Regenerating the root lockfile would fix it at the source, but that also
# re-resolves every frontend dependency, so it is deliberately not done here.
# npm hoists `next` to the root node_modules of the workspace, so resolve it
# by module name (with the nested path as a fallback for a non-hoisted
# install) -- reading apps/web/node_modules/next directly fails with
# MODULE_NOT_FOUND on a hoisted tree, which is every tree npm produces here.
RUN NEXT_VERSION="$(node -p "require('next/package.json').version" 2>/dev/null || node -p "require('./apps/web/node_modules/next/package.json').version")" && npm install --no-save --ignore-scripts --workspace=apps/web "@next/swc-linux-x64-musl@${NEXT_VERSION}"

COPY packages/shared packages/shared
COPY apps/web apps/web

# @trace-x/shared is consumed through its "main"/"types" (dist/), so it must be
# compiled before the web app can import it.
RUN npm run build --workspace=packages/shared --if-present

WORKDIR /app/apps/web

EXPOSE 3000

CMD ["npm", "run", "dev"]
