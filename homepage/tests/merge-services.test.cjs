const test = require('node:test');
const assert = require('node:assert/strict');
const { mergeGroups } = require('../scripts/merge-services.cjs');

test('common services work without additions and retain group order', () => {
  const base = [{ Players: [{ Player: { href: 'http://player' } }] }];
  assert.deepEqual(mergeGroups(base, []), base);
});

test('extras append to matching groups and leave source objects unchanged', () => {
  const base = [{ Players: [{ Player: { href: 'http://player' } }] }];
  const extra = [{ Players: [{ Additional: { href: 'http://extra' } }] }, { Tools: [] }];
  const original = structuredClone([base, extra]);
  const merged = mergeGroups(base, extra);
  assert.deepEqual(merged, [{ Players: [...base[0].Players, ...extra[0].Players] }, { Tools: [] }]);
  assert.deepEqual([base, extra], original);
});

test('duplicates and malformed configuration are rejected', () => {
  const base = [{ Players: [{ Player: {} }] }];
  assert.throws(() => mergeGroups(base, base), /Duplicate/);
  assert.throws(() => mergeGroups({}, []), /list/);
  assert.throws(() => mergeGroups([{ Players: {} }], []), /list/);
});

test('source links follow additions and deletions without removing runtime state', () => {
  const fs = require('node:fs');
  const os = require('node:os');
  const path = require('node:path');
  const { syncSourceLinks } = require('../scripts/merge-services.cjs');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'homepage-links-'));
  const source = path.join(root, 'source');
  const output = path.join(root, 'output');
  fs.mkdirSync(source);
  fs.mkdirSync(output);
  try {
    fs.writeFileSync(path.join(source, 'settings.yaml'), 'theme: dark');
    fs.writeFileSync(path.join(output, 'cache.txt'), 'runtime');
    syncSourceLinks(source, output);
    assert.equal(fs.readFileSync(path.join(output, 'settings.yaml'), 'utf8'), 'theme: dark');
    fs.unlinkSync(path.join(source, 'settings.yaml'));
    syncSourceLinks(source, output);
    assert.equal(fs.readdirSync(output).includes('settings.yaml'), false);
    assert.equal(fs.readFileSync(path.join(output, 'cache.txt'), 'utf8'), 'runtime');
    fs.writeFileSync(path.join(output, 'widgets.yaml'), 'native default');
    fs.writeFileSync(path.join(source, 'widgets.yaml'), 'custom source');
    syncSourceLinks(source, output);
    assert.equal(fs.readFileSync(path.join(output, 'widgets.yaml'), 'utf8'), 'custom source');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
