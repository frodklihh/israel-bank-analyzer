// bridge.js — JSON-in / JSON-out wrapper around israeli-bank-scrapers.
//
// Reads a single JSON request from stdin:
//   {
//     "provider":     "hapoalim" | "isracard" | "leumi" | "visaCal",
//     "credentials":  { ...provider-specific fields },
//     "startDate":    "YYYY-MM-DD",
//     "showBrowser":  true,
//     "combineInstallments": false,
//     "timeout":      120000        // optional, ms
//   }
//
// Writes a single JSON response to stdout:
//   {
//     "success": true,
//     "accounts": [
//       {
//         "accountNumber": "...",
//         "balance": 0.0,
//         "txns": [ { date, processedDate, originalAmount, originalCurrency,
//                     chargedAmount, description, status, ... } ]
//       }
//     ]
//   }
//
// On error:
//   { "success": false, "errorType": "...", "errorMessage": "..." }
//
// Status messages from the scraper go to stderr so they don't corrupt stdout.

import { CompanyTypes, createScraper } from 'israeli-bank-scrapers';

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

function logStatus(msg) {
  // Anything not a structured stdout JSON goes to stderr.
  process.stderr.write(`[bridge] ${msg}\n`);
}

async function main() {
  const raw = await readStdin();
  let req;
  try {
    req = JSON.parse(raw);
  } catch (e) {
    process.stdout.write(JSON.stringify({
      success: false,
      errorType: 'BAD_REQUEST',
      errorMessage: `stdin is not valid JSON: ${e.message}`,
    }));
    process.exit(2);
  }

  const {
    provider,
    credentials,
    startDate,
    showBrowser = true,
    combineInstallments = false,
    timeout,
  } = req;

  if (!provider || !CompanyTypes[provider]) {
    process.stdout.write(JSON.stringify({
      success: false,
      errorType: 'BAD_PROVIDER',
      errorMessage: `Unknown provider '${provider}'. Available: ${Object.keys(CompanyTypes).join(', ')}`,
    }));
    process.exit(2);
  }

  const options = {
    companyId: CompanyTypes[provider],
    startDate: new Date(startDate),
    combineInstallments,
    showBrowser,
  };
  if (typeof timeout === 'number') {
    options.timeout = timeout;
  }

  logStatus(`provider=${provider} startDate=${startDate} showBrowser=${showBrowser}`);

  const scraper = createScraper(options);

  // Forward progress events to stderr so the Python side can show them live.
  scraper.onProgress((companyId, payload) => {
    logStatus(`progress: ${companyId} → ${payload.type}`);
  });

  let result;
  try {
    result = await scraper.scrape(credentials);
  } catch (e) {
    process.stdout.write(JSON.stringify({
      success: false,
      errorType: 'SCRAPER_THREW',
      errorMessage: e && e.message ? e.message : String(e),
    }));
    process.exit(1);
  }

  // result already has shape { success, errorType, errorMessage, accounts }
  process.stdout.write(JSON.stringify(result));
  process.exit(result.success ? 0 : 1);
}

main().catch((e) => {
  process.stdout.write(JSON.stringify({
    success: false,
    errorType: 'BRIDGE_CRASH',
    errorMessage: e && e.message ? e.message : String(e),
  }));
  process.exit(3);
});
