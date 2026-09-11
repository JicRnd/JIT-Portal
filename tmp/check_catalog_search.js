// Focused verification harness: loads the real search helpers out of
// parts_catalog.html and runs them against live Pricing.db part rows.
const fs = require('fs');
const path = require('path');

const templatePath = path.join(__dirname, '..', 'Cylinder_Quote_Web_Milestone_1', 'app', 'templates', 'parts_catalog.html');
const html = fs.readFileSync(templatePath, 'utf8');
const start = html.indexOf('const CATEGORY_SEARCHES');
const end = html.indexOf('function partText(row)');
if (start < 0 || end < 0) throw new Error('Could not locate search helpers in template');
const source = html.slice(start, end);

const sandbox = {};
new Function(`${source}; Object.assign(this, { CATEGORY_SEARCHES, GROUP_RULES, canonical, tokens, matchingCategory, qualifierRules });`).call(sandbox);
const { canonical, tokens, matchingCategory, qualifierRules } = sandbox;

const parts = JSON.parse(fs.readFileSync(path.join(__dirname, 'parts_dump.json'), 'utf8'))
    .map((row) => ({ ...row, text: canonical(`${row.part_number || ''} ${row.description || ''}`) }));

function search(query) {
    const queryTokens = tokens(query);
    const resolved = matchingCategory(query);
    if (!queryTokens.length) return parts;
    if (!resolved) return parts.filter((row) => queryTokens.every((token) => row.text.includes(token)));
    const { category, qualifiers } = resolved;
    const rules = qualifiers.length ? qualifierRules(category, qualifiers) : [];
    return parts.filter((row) => {
        if (!category.terms.some((term) => row.text.includes(canonical(term)))) return false;
        if (!qualifiers.length) return true;
        if (rules.some((rule) => rule.terms.some((term) => row.text.includes(canonical(term))))) return true;
        return qualifiers.every((token) => row.text.includes(token));
    });
}

const queries = ['seals', 'viton seals', 'seals viton', 'viton seal', 'buna seals', 'nitrile seals',
    'low friction seals', 'piston seals', 'rod seals', 'wipers', 'pistons', 'barrels', 'tie rods',
    'mounts', 'jam nuts'];

for (const query of queries) {
    const hits = search(query);
    const sample = hits.slice(0, 2).map((row) => `${row.part_number} :: ${row.description || ''}`).join(' | ');
    console.log(`${query.padEnd(20)} ${String(hits.length).padStart(5)}   ${sample}`);
}
console.log(`${'seals vs seals viton'.padEnd(20)} order-independent: ${search('viton seals').length === search('seals viton').length}`);
console.log(`${'plural check'.padEnd(20)} viton seal == viton seals: ${search('viton seal').length === search('viton seals').length}`);
