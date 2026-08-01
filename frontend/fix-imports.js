const fs = require('fs');
const path = require('path');
function walk(d) {
  const f = fs.readdirSync(d);
  for (const i of f) {
    const p = path.join(d, i);
    if (fs.statSync(p).isDirectory()) { walk(p); }
    else if (p.endsWith('.tsx') || p.endsWith('.ts')) {
      let c = fs.readFileSync(p, 'utf8');
      let changed = false;
      if (c.includes('@/lib/utils')) { c = c.replaceAll('@/lib/utils', '@/app/lib/utils'); changed = true; }
      if (c.includes('@/store/useAuthStore')) { c = c.replaceAll('@/store/useAuthStore', '@/app/store/useAuthStore'); changed = true; }
      if (changed) { fs.writeFileSync(p, c); console.log('Fixed: ' + p); }
    }
  }
}
walk('src');
