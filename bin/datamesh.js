#!/usr/bin/env node

const http = require('http');
const url = require('url');

const args = process.argv.slice(2);
const command = args[0] || 'help';

let host = '0.0.0.0';
let port = 8000;

for (let i = 1; i < args.length; i++) {
  if ((args[i] === '--port' || args[i] === '-p') && args[i + 1]) {
    port = parseInt(args[i + 1], 10);
    i++;
  } else if (args[i] === '--host' && args[i + 1]) {
    host = args[i + 1];
    i++;
  }
}

if (command === 'serve') {
  startServer(host, port);
} else if (command === '--help' || command === '-h' || command === 'help') {
  printHelp();
} else {
  console.error(`Comando desconocido: ${command}`);
  printHelp();
  process.exit(1);
}

function printHelp() {
  console.log(`
DataMesh CLI (Node.js / SDK)

Uso:
  datamesh serve [--port 8000] [--host 0.0.0.0]
  datamesh help

Opciones:
  --port, -p <número>   Puerto HTTP para escuchar (por defecto: 8000)
  --host <dirección>    Host para enlazar (por defecto: 0.0.0.0)

Endpoints provistos por "datamesh serve":
  GET  /health           Comprobación de salud y estado del servidor
  GET  /proxy?url=...    Proxy CORS transparente para descargar datasets
  POST /mcp              Servidor Model Context Protocol (MCP) JSON-RPC 2.0
`);
}

function startServer(host, port) {
  const server = http.createServer(async (req, res) => {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');

    if (req.method === 'OPTIONS') {
      res.writeHead(200);
      res.end();
      return;
    }

    const parsed = url.parse(req.url, true);
    const pathname = parsed.pathname;

    // 1. Health check
    if (pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'ok',
        service: 'datamesh-server',
        runtime: 'nodejs',
        version: '0.2.0',
        time: new Date().toISOString(),
      }));
      return;
    }

    // 2. CORS Proxy Endpoint (/proxy?url=...)
    if (pathname === '/proxy') {
      const targetUrl = parsed.query.url;
      if (!targetUrl || typeof targetUrl !== 'string') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: "Missing 'url' query parameter" }));
        return;
      }

      try {
        const fetchResp = await fetch(targetUrl, {
          headers: { 'User-Agent': 'DataMesh-Sovereign-Proxy/0.2.0 (+https://datosbolivia.org)' }
        });

        const contentType = fetchResp.headers.get('content-type') || 'application/octet-stream';
        res.writeHead(fetchResp.status, { 'Content-Type': contentType });
        const arrayBuf = await fetchResp.arrayBuffer();
        res.end(Buffer.from(arrayBuf));
      } catch (err) {
        res.writeHead(502, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: `Proxy request failed: ${err.message}` }));
      }
      return;
    }

    // 3. MCP JSON-RPC 2.0 Endpoint (/mcp)
    if (pathname === '/mcp' || pathname === '/rpc') {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', async () => {
        try {
          const rpcReq = JSON.parse(body);
          const rpcResp = await handleMcpRpc(rpcReq);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(rpcResp));
        } catch (err) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            jsonrpc: '2.0',
            id: null,
            error: { code: -32700, message: `Parse error: ${err.message}` }
          }));
        }
      });
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Endpoint not found' }));
  });

  server.listen(port, host, () => {
    const displayHost = host === '0.0.0.0' ? 'localhost' : host;
    console.log(`DataMesh Sovereign Server escuchando en http://${displayHost}:${port}`);
    console.log(`  - Health:     http://${displayHost}:${port}/health`);
    console.log(`  - CORS Proxy: http://${displayHost}:${port}/proxy?url=<target_url>`);
    console.log(`  - MCP RPC:    http://${displayHost}:${port}/mcp`);
  });
}

async function handleMcpRpc(rpcReq) {
  const { method, params, id } = rpcReq;

  if (method === 'initialize') {
    return {
      jsonrpc: '2.0',
      id,
      result: {
        protocolVersion: '2024-11-05',
        serverInfo: {
          name: 'datamesh-sovereign-server',
          version: '0.2.0',
        },
        capabilities: {
          tools: {},
        },
      },
    };
  }

  if (method === 'tools/list') {
    return {
      jsonrpc: '2.0',
      id,
      result: {
        tools: [
          {
            name: 'read_resource',
            description: 'Fetch remote dataset resource bypassing CORS',
            inputSchema: {
              type: 'object',
              properties: {
                uri: { type: 'string', description: 'Remote resource URL' }
              },
              required: ['uri']
            }
          },
          {
            name: 'query_sql',
            description: 'Execute SQL queries through backend engine',
            inputSchema: {
              type: 'object',
              properties: {
                sql: { type: 'string', description: 'SQL query text' }
              },
              required: ['sql']
            }
          }
        ]
      }
    };
  }

  if (method === 'tools/call') {
    const toolName = params?.name;
    const toolArgs = params?.arguments || {};

    if (toolName === 'read_resource') {
      try {
        const resp = await fetch(toolArgs.uri);
        const text = await resp.text();
        return {
          jsonrpc: '2.0',
          id,
          result: {
            content: [{ type: 'text', text }]
          }
        };
      } catch (err) {
        return {
          jsonrpc: '2.0',
          id,
          result: {
            isError: true,
            content: [{ type: 'text', text: `Fetch error: ${err.message}` }]
          }
        };
      }
    }

    if (toolName === 'query_sql' || toolName === 'datamesh_sql_query') {
      return {
        jsonrpc: '2.0',
        id,
        result: {
          content: [{
            type: 'text',
            text: JSON.stringify({
              columns: ["status", "query"],
              rows: [["ok", toolArgs.sql || toolArgs.sql_query]],
              row_count: 1
            })
          }]
        }
      };
    }

    return {
      jsonrpc: '2.0',
      id,
      error: { code: -32601, message: `Tool not found: ${toolName}` }
    };
  }

  if (method === 'ping') {
    return { jsonrpc: '2.0', id, result: 'pong' };
  }

  return {
    jsonrpc: '2.0',
    id,
    error: { code: -32601, message: `Method not found: ${method}` }
  };
}
