/* Merge optional dashboard entries using the YAML parser bundled with Homepage. */
const fs = require('node:fs');
const path = require('node:path');

function mergeGroups(base, extra) {
  const result = [];
  const groups = new Map();
  for (const source of [base, extra]) {
    if (!Array.isArray(source)) throw new Error('Services must be a list of groups');
    for (const row of source) {
      if (!row || typeof row !== 'object' || Array.isArray(row) || Object.keys(row).length !== 1) {
        throw new Error('Each group must have exactly one name');
      }
      const [name, services] = Object.entries(row)[0];
      if (!Array.isArray(services)) throw new Error('Each group must contain a list of services');
      if (!groups.has(name)) {
        const entries = [];
        groups.set(name, entries);
        result.push({ [name]: entries });
      }
      const entries = groups.get(name);
      for (const service of services) {
        if (!service || typeof service !== 'object' || Array.isArray(service) || Object.keys(service).length !== 1) {
          throw new Error('Each service must have exactly one name');
        }
        const key = Object.keys(service)[0];
        if (entries.some(entry => Object.hasOwn(entry, key))) {
          throw new Error('Duplicate service in a dashboard group');
        }
        entries.push(structuredClone(service));
      }
    }
  }
  return result;
}

function syncSourceLinks(source, output) {
  // Remove only links managed by this renderer when their source disappears.
  for (const entry of fs.readdirSync(output, { withFileTypes: true })) {
    if (!entry.isSymbolicLink()) continue;
    const target = path.join(output, entry.name);
    const expected = path.join(source, entry.name);
    if (fs.readlinkSync(target) === expected && !fs.existsSync(expected)) fs.unlinkSync(target);
  }
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    if (entry.name === 'services.yaml' || entry.name === 'logs') continue;
    const target = path.join(output, entry.name);
    const expected = path.join(source, entry.name);
    let current;
    try { current = fs.lstatSync(target); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (current?.isSymbolicLink() && fs.readlinkSync(target) === expected) continue;
    if (current) {
      if (current.isDirectory()) throw new Error('Generated config path conflicts with a directory');
      fs.unlinkSync(target);
    }
    fs.symlinkSync(expected, target);
  }
}

function render() {
  const yaml = require('js-yaml');
  const source = process.env.HOMEPAGE_SOURCE_DIR || '/app/config-source';
  const output = process.env.HOMEPAGE_OUTPUT_DIR || '/app/config';
  const extras = process.env.HOMEPAGE_EXTRAS_DIR || '/app/config-extra';
  const baseFile = path.join(source, 'services.yaml');
  const extraFile = path.join(extras, 'services.yaml');
  const base = yaml.load(fs.readFileSync(baseFile, 'utf8')) || [];
  const extra = fs.existsSync(extraFile) ? yaml.load(fs.readFileSync(extraFile, 'utf8')) || [] : [];
  const combined = yaml.dump(mergeGroups(base, extra), { lineWidth: -1, noRefs: true });
  fs.mkdirSync(output, { recursive: true });
  syncSourceLinks(source, output);
  const target = path.join(output, 'services.yaml');
  if (!fs.existsSync(target) || fs.readFileSync(target, 'utf8') !== combined) {
    const temporary = `${target}.${process.pid}.tmp`;
    fs.writeFileSync(temporary, combined, { mode: 0o600 });
    fs.renameSync(temporary, target);
  }
}

if (require.main === module) {
  try {
    render();
    if (process.argv.includes('--watch')) {
      let timer;
      const update = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          try { render(); }
          catch { console.error('Homepage configuration update rejected; previous output preserved.'); }
        }, 250);
      };
      for (const directory of [process.env.HOMEPAGE_SOURCE_DIR || '/app/config-source',
                               process.env.HOMEPAGE_EXTRAS_DIR || '/app/config-extra']) {
        if (fs.existsSync(directory)) fs.watch(directory, update);
      }
    }
  } catch {
    console.error('Homepage configuration merge failed; check source YAML and duplicate names.');
    process.exitCode = 1;
  }
}

module.exports = { mergeGroups, syncSourceLinks, render };
