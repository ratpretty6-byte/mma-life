const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.json': 'application/json',
  '.txt': 'text/plain', '.svg': 'image/svg+xml'
};

function handler(req, res) {
  let fp = req.url === '/' ? 'index.html' : req.url.slice(1);
  let fpFull = path.join('/workspace/MMALIFE/templates', fp);
  try {
    if (fs.existsSync(fpFull) && fs.statSync(fpFull).isFile()) {
      let ct = MIME[path.extname(fpFull)] || 'application/octet-stream';
      res.writeHead(200, {
        'Content-Type': ct,
        'Access-Control-Allow-Origin': '*',
        'X-Content-Type-Options': 'nosniff'
      });
      res.end(fs.readFileSync(fpFull));
    } else {
      res.writeHead(404, {'Content-Type': 'text/plain'});
      res.end('Not found: ' + req.url);
    }
  } catch(e) {
    res.writeHead(500, {'Content-Type': 'text/plain'});
    res.end('Error: ' + e.message);
  }
}

// HTTP on 8080
http.createServer(handler).listen(8080, '0.0.0.0', () => {
  console.log('HTTP on 8080');
});

// HTTPS on 8443
const key = fs.readFileSync('/tmp/key.pem');
const cert = fs.readFileSync('/tmp/cert.pem');
https.createServer({key, cert}, handler).listen(8443, '0.0.0.0', () => {
  console.log('HTTPS on 8443');
});
