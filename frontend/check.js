const fs = require('fs');
const c = fs.readFileSync('src/app/roadmap/page.tsx', 'utf8');
const lines = c.split(/\r?\n/);
console.log('Line 74: ' + JSON.stringify(lines[73]));
console.log('Has double quotes: ' + c.includes('variant= primary'));
console.log('Has single quotes: ' + c.includes(variant=primary));
