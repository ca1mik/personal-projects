const http = require('node:http');

const upstream = 'http://127.0.0.1:8088';
const port = 8089;
const blockedPath = /(?:^|\/)(?:wp-admin|wp-json|wp-login\.php|xmlrpc\.php|wp-cron\.php|wp-config\.php|readme\.html|license\.txt)(?:\/|$)/i;
const privateFile = /\.(?:php|sqlite|db|sql|ini|log|bak|zip|phar)(?:$|\/)/i;
const textType = /^(?:text\/|application\/(?:json|javascript|xml|xhtml\+xml))/i;

http.createServer((request, response) => {
    let url;
    try {
        url = new URL(request.url, upstream);
    } catch {
        response.writeHead(400).end();
        return;
    }

    let decodedPath;
    try {
        decodedPath = decodeURIComponent(url.pathname);
    } catch {
        response.writeHead(400).end();
        return;
    }

    const forbiddenQuery = [...url.searchParams.keys()].some((key) => /^(?:add-to-cart|wc-ajax|rest_route|preview|customize_changeset_uuid)$/i.test(key));
    if (!['GET', 'HEAD'].includes(request.method) || blockedPath.test(decodedPath) || privateFile.test(decodedPath) || forbiddenQuery) {
        response.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Preview is read-only.');
        return;
    }

    const host = request.headers.host || '';
    const publicHost = /^[a-z0-9-]+\.trycloudflare\.com$/i.test(host);
    const localHost = /^(?:127\.0\.0\.1|localhost):8089$/i.test(host);
    if (!publicHost && !localHost) {
        response.writeHead(400).end();
        return;
    }
    const origin = publicHost ? `https://${host}` : `http://${host}`;
    const headers = { ...request.headers, host: '127.0.0.1:8088', 'accept-encoding': 'identity' };
    delete headers.cookie;
    delete headers['cf-connecting-ip'];
    delete headers['x-forwarded-host'];
    delete headers['x-forwarded-proto'];

    const upstreamRequest = http.request(`${upstream}${url.pathname}${url.search}`, { method: request.method, headers }, (upstreamResponse) => {
        const outgoingHeaders = { ...upstreamResponse.headers, 'x-robots-tag': 'noindex, nofollow, noarchive', 'cache-control': 'no-store' };
        delete outgoingHeaders['set-cookie'];
        if (outgoingHeaders.location) {
            outgoingHeaders.location = outgoingHeaders.location.replaceAll(upstream, origin);
        }
        if (!textType.test(String(upstreamResponse.headers['content-type'] || '')) || request.method === 'HEAD') {
            response.writeHead(upstreamResponse.statusCode, outgoingHeaders);
            upstreamResponse.pipe(response);
            return;
        }

        const chunks = [];
        upstreamResponse.on('data', (chunk) => chunks.push(chunk));
        upstreamResponse.on('end', () => {
            const body = Buffer.from(Buffer.concat(chunks).toString('utf8').replaceAll(upstream, origin));
            delete outgoingHeaders['content-encoding'];
            delete outgoingHeaders['transfer-encoding'];
            outgoingHeaders['content-length'] = body.length;
            response.writeHead(upstreamResponse.statusCode, outgoingHeaders).end(body);
        });
    });

    upstreamRequest.on('error', () => response.writeHead(502).end('Local WordPress is unavailable.'));
    upstreamRequest.end();
}).listen(port, '127.0.0.1', () => {
    process.stdout.write(`Preview proxy listening on http://127.0.0.1:${port}/\n`);
});
