#!/usr/bin/env node
/*
 * web_matches_python.js
 *
 * Runs the synthetic CVR files in testCases/generated/ through both versions
 * of the anonymizer, the Python command line (anonymize_cvr.py) and the
 * JavaScript in the web page (anonymize_cvr.html), and checks that they write
 * byte-for-byte the same output, or that neither writes one.
 *
 * The page's scripts are loaded into a Node vm context.  The page's UI code
 * only runs when a document is present, so none is needed; runAnonymizer()
 * is called directly with an in-memory file and an in-memory writable stream.
 *
 * The web version has no --check mode and no --stylecol, so those are not
 * compared.
 *
 * Usage (from the repository root):
 *     node tests/web_matches_python.js
 * Exit status 0 if every case matches, 1 otherwise.
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const GENERATED = path.join(ROOT, 'testCases', 'generated');
const PYTHON = process.env.PYTHON || 'python3';

// [file, Python flags].  The web options are derived from the flags.
const CASES = [
    ['no_redaction.csv', []],
    ['needs_borrowing.csv', []],
    ['needs_borrowing.csv', ['--no-contest-balancing']],
    ['rare_unique_contest.csv', []],
    ['near_unanimous_fixable.csv', []],
    ['near_unanimous_fixable.csv', ['--no-contest-balancing']],
    ['near_unanimous_unavoidable.csv', []],
    ['precinct_redaction.csv', ['--redact-on-precinct']],
    ['ballot_type_present.csv', []],
    ['ballot_type_present.csv', ['--drop-ballottype']],
    ['named_style.csv', []],
    ['blocked_style.csv', []],
    ['rare_contest.csv', []],
    ['rare_contest.csv', ['--keep-rare-contests']],
    ['rare_contest.csv', ['--no-contest-balancing']],
    ['rare_contest_only.csv', []],
    ['rare_contest_only.csv', ['--keep-rare-contests']],
    ['county_blanked_contest.csv', []],
    ['rare_ballot_type.csv', []],
    ['rare_ballot_type.csv', ['--drop-ballottype']],
    ['rare_ballot_type.csv', ['--no-contest-balancing']],
];

function loadWebVersion() {
    const html = fs.readFileSync(path.join(ROOT, 'anonymize_cvr.html'), 'utf8');
    const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
    if (scripts.length === 0) throw new Error('no <script> blocks in anonymize_cvr.html');
    const context = vm.createContext({
        console, TextDecoder, TextEncoder, Uint8Array, Blob, setTimeout, clearTimeout,
    });
    scripts.forEach((code, i) =>
        vm.runInContext(code, context, { filename: `anonymize_cvr.html<script ${i + 1}>` }));
    // Papa.parse reads a File with FileReader, which Node lacks; hand it the
    // text instead.  Pass 3 reads the same object with .stream(), as a Blob.
    vm.runInContext(`
        const parseFile = Papa.parse;
        Papa.parse = (input, config) =>
            parseFile(input && input.cvrText !== undefined ? input.cvrText : input, config);
    `, context);
    return context;
}

async function runWeb(web, inputPath, flags) {
    const text = fs.readFileSync(inputPath, 'utf8');
    const file = new Blob([text]);
    file.cvrText = text;
    const chunks = [];
    let closed = false, aborted = false;
    const writable = {
        async write(s) { chunks.push(s); },
        async close() { closed = true; },
        async abort() { aborted = true; },
    };
    const options = {
        minBallots: 10,
        redactOnPrecinct: flags.includes('--redact-on-precinct'),
        noContestBalancing: flags.includes('--no-contest-balancing'),
        keepRareContests: flags.includes('--keep-rare-contests'),
        dropBallotType: flags.includes('--drop-ballottype'),
    };
    const log = [];
    const wrote = await web.runAnonymizer(file, options, writable, m => log.push(m));
    if (wrote !== closed || aborted === wrote)
        throw new Error('runAnonymizer left the writable in an unexpected state');
    return { output: wrote ? chunks.join('') : null, log: log.join('\n') };
}

function runPython(inputPath, flags, outDir, n) {
    const outPath = path.join(outDir, `python_${n}.csv`);
    const log = execFileSync(
        PYTHON, [path.join(ROOT, 'anonymize_cvr.py'), ...flags, inputPath, outPath],
        { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    return {
        output: fs.existsSync(outPath) ? fs.readFileSync(outPath, 'utf8') : null,
        log,
    };
}

function firstDifference(a, b) {
    const la = a.split('\n'), lb = b.split('\n');
    for (let i = 0; i < Math.max(la.length, lb.length); i++)
        if (la[i] !== lb[i])
            return `line ${i + 1}:\n      python: ${JSON.stringify(la[i])}\n      web:    ${JSON.stringify(lb[i])}`;
    return '(no line differs)';
}

async function main() {
    if (!fs.existsSync(GENERATED))
        execFileSync(PYTHON, ['generate_test_cvrs.py'], { cwd: ROOT, stdio: 'ignore' });
    const web = loadWebVersion();
    const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'anonymize-web-'));
    let passed = 0, failed = 0;
    try {
        for (const [n, [name, flags]] of CASES.entries()) {
            const label = [name, ...flags].join(' ');
            const input = path.join(GENERATED, name);
            const py = runPython(input, flags, outDir, n);
            const js = await runWeb(web, input, flags);
            let problem = null;
            if ((py.output === null) !== (js.output === null))
                problem = `python ${py.output === null ? 'wrote nothing' : 'wrote a file'}, ` +
                          `web ${js.output === null ? 'wrote nothing' : 'wrote a file'}`;
            else if (py.output !== null && py.output !== js.output)
                problem = 'outputs differ at ' + firstDifference(py.output, js.output);
            if (problem) {
                failed++;
                console.log(`FAIL  web == python: ${label}\n    ${problem}`);
            } else {
                passed++;
                console.log(`PASS  web == python: ${label}` +
                            (py.output === null ? ' (no output from either)' : ''));
            }
        }
    } finally {
        fs.rmSync(outDir, { recursive: true, force: true });
    }
    console.log(`\nWeb cross-check: ${passed} passed, ${failed} failed.`);
    process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => { console.error(err); process.exit(1); });
