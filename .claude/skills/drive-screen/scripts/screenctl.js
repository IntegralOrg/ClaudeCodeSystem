#!/usr/bin/osascript -l JavaScript
// screenctl.js - screen control for a Mac before python3 exists.
//
// The drive-screen skill's driver is screenctl.py. A clean Mac has no python3 until
// the Command Line Tools finish installing, and the first minutes of setup need
// two things before then: raise the Accessibility and Screen Recording prompts for
// the right app, and click Install and Agree on the tools installer. This file does
// only that, with the same first-token output as screenctl.py, so the setup
// procedure reads the same. The moment python3 runs, use screenctl.py.
//
//   osascript -l JavaScript screenctl.js doctor
//   osascript -l JavaScript screenctl.js request
//   osascript -l JavaScript screenctl.js shot  --title "Install Command Line" --out /tmp/a.png
//   osascript -l JavaScript screenctl.js click --title "Install Command Line" --button Install
//   osascript -l JavaScript screenctl.js click --title "..." --x 850 --y 730
//   osascript -l JavaScript screenctl.js key   --title "..." --keys enter
//   osascript -l JavaScript screenctl.js handback [--text "..."] [--quiet]
//
// Exit codes: 0 ok, 1 refused (not found, ambiguous, focus unconfirmed, bad input).
// Every action re-verifies the foreground app before sending, and refuses instead
// of sending when it does not match: a keystroke goes wherever focus is.

ObjC.import('stdlib');
ObjC.import('CoreGraphics');
ObjC.import('ApplicationServices');
// The bridge has no metadata for these C functions, so they are bound by hand:
// an unbound one is "undefined is not a function" at the first permission check.
ObjC.bindFunction('CGPreflightPostEventAccess', ['bool', []]);
ObjC.bindFunction('CGRequestPostEventAccess', ['bool', []]);
ObjC.bindFunction('CGPreflightScreenCaptureAccess', ['bool', []]);
ObjC.bindFunction('CGRequestScreenCaptureAccess', ['bool', []]);
ObjC.bindFunction('AXIsProcessTrusted', ['bool', []]);
ObjC.bindFunction('AXIsProcessTrustedWithOptions', ['bool', ['id']]);

var COMMANDS = ['doctor', 'request', 'shot', 'click', 'key', 'handback'];
var CLAUDE_BUNDLE_ID = 'com.anthropic.claudefordesktop';
var OWNER = 'permissions_belong_to: Claude Code   (when run from Claude Desktop; grant this app, not Claude)';
var app = Application.currentApplication();
app.includeStandardAdditions = true;
var se = Application('System Events');

function out(line) {
  $.NSFileHandle.fileHandleWithStandardOutput.writeData(
    $(String(line) + '\n').dataUsingEncoding($.NSUTF8StringEncoding));
}
function die(code, msg) { out(code + ': ' + msg); $.exit(1); }
function q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }
function sh(cmd) { try { return app.doShellScript(cmd); } catch (e) { return null; } }

function parse(argv) {
  var a = {cmd: argv[0], flags: {}};
  for (var i = 1; i < argv.length; i++) {
    var k = argv[i];
    if (k.indexOf('--') !== 0) continue;
    var n = argv[i + 1];
    if (n === undefined || n.indexOf('--') === 0) { a.flags[k.slice(2)] = true; }
    else { a.flags[k.slice(2)] = n; i++; }
  }
  return a;
}
function usage() {
  out('screenctl.js <' + COMMANDS.join('|') + '> [--title T] [--out F] [--max-width N] [--button NAME] [--x N --y N] [--keys K] [--text T] [--quiet]');
  out('The screen driver for a Mac before python3 exists. Use screenctl.py once python3 runs.');
}

// ---- windows -------------------------------------------------------------
function listWindows() {
  var found = [];
  var procs = se.applicationProcesses.whose({visible: true});
  for (var i = 0; i < procs.length; i++) {
    var p = procs[i], pname, wins;
    try { pname = p.name(); wins = p.windows(); } catch (e) { continue; }
    for (var j = 0; j < wins.length; j++) {
      try {
        var pos = wins[j].position(), sz = wins[j].size();
        found.push({proc: pname, idx: j, title: wins[j].name() || pname,
                    x: pos[0], y: pos[1], w: sz[0], h: sz[1]});
      } catch (e) {}
    }
  }
  return found;
}
function systemEventsState() {
  // Process names are readable without the grant; window attributes are not.
  // Finder always has readable windows when the grant is in place. Two different
  // refusals look alike from here: no Accessibility grant, and the person
  // clicking Don't Allow on the "control System Events" prompt (error -1743),
  // which switching Accessibility on cannot cure.
  try { se.applicationProcesses.byName('Finder').windows.length; return 'ok'; }
  catch (e) {
    var msg = String(e.message || e);
    return (e.errorNumber === -1743 || msg.indexOf('-1743') >= 0 || msg.indexOf('Not authorized') >= 0) ? 'automation' : 'accessibility';
  }
}
var AUTOMATION_HELP = 'macOS did not allow this app to control System Events (error -1743). The person clicks OK on that prompt, or switches Claude Code on under Automation in System Settings > Privacy & Security.';
function accessibilityDenied() { return systemEventsState() !== 'ok'; }
function resolve(title) {
  if (!title) die('NO_TITLE', '--title is required for this action');
  var t = String(title).toLowerCase();
  var hits = listWindows().filter(function (w) {
    return w.title.toLowerCase().indexOf(t) >= 0 || w.proc.toLowerCase().indexOf(t) >= 0;
  });
  if (!hits.length) {
    var state = systemEventsState();
    if (state === 'automation') die('AUTOMATION_DENIED', AUTOMATION_HELP);
    if (state === 'accessibility') die('NO_ACCESSIBILITY', 'System Events is not allowed assistive access. Run: screenctl.js request');
    die('NOT_FOUND', 'no visible window title or app name contains "' + title + '"');
  }
  if (hits.length > 1) die('AMBIGUOUS', '"' + title + '" matches ' + hits.length + ' visible windows. Pass a longer --title.');
  return hits[0];
}
function frontProc() {
  try { return se.applicationProcesses.whose({frontmost: true})[0].name(); } catch (e) { return ''; }
}
function focus(win) {
  var p = se.applicationProcesses.byName(win.proc);
  for (var attempt = 0; attempt < 2; attempt++) {
    try { p.frontmost = true; p.windows[win.idx].actions.byName('AXRaise').perform(); } catch (e) {}
    delay(0.45);
    if (frontProc() === win.proc) { out('FOCUS_OK: ' + win.title); return; }
  }
  die('FOCUS_FAILED', 'wanted "' + win.title + '", foreground is "' + frontProc() + '". Nothing was sent.');
}

// ---- commands ------------------------------------------------------------
function pngSize(path) {
  var w = sh('/usr/bin/sips -g pixelWidth ' + q(path) + " 2>/dev/null | /usr/bin/awk '/pixelWidth/ {print $2}'");
  var h = sh('/usr/bin/sips -g pixelHeight ' + q(path) + " 2>/dev/null | /usr/bin/awk '/pixelHeight/ {print $2}'");
  return [parseInt(w || '0', 10) || 0, parseInt(h || '0', 10) || 0];
}
function shot(f) {
  if (!f.out) die('NO_OUT', '--out is required for shot');
  var win = resolve(f.title);
  // Without the grant the capture still exits 0 and writes a picture of the
  // wallpaper, so the grant is checked first, never inferred from the file.
  if (!$.CGPreflightScreenCaptureAccess()) die('NO_SCREEN_RECORDING', 'Screen Recording is not granted to this session. A switch turned on during this session takes effect in a new one: tell the person what to click instead of reading the screen.');
  focus(win);
  delay(1.0);
  sh('/usr/sbin/screencapture -x -o -R' + [win.x, win.y, win.w, win.h].join(',') + ' ' + q(f.out));
  var size = pngSize(f.out);
  if (!size[0]) die('CAPTURE_FAILED', 'screencapture produced no readable PNG. If Screen Recording was switched on during this session, it may only take effect in a new session: tell the person what to click instead.');
  var maxw = parseInt(f['max-width'] || '1280', 10);
  if (maxw && size[0] > maxw) { sh('/usr/bin/sips -Z ' + maxw + ' ' + q(f.out) + ' >/dev/null 2>&1'); size = pngSize(f.out); }
  var scale = win.w ? size[0] / win.w : 1;
  out('SHOT: ' + f.out + '  ' + size[0] + 'x' + size[1]);
  out('WINDOW_ORIGIN: ' + win.x + ',' + win.y + '    IMAGE_SCALE: ' + scale.toFixed(4));
  out('To click what you see at image pixel (px,py), pass:');
  out('  --x ' + win.x + ' + px/' + scale.toFixed(4) + '    --y ' + win.y + ' + py/' + scale.toFixed(4));
  out('A picture that is one flat colour means Screen Recording is not live in this session. Do not reason about it.');
}
function clickByName(win, name) {
  // Accessibility only, no screenshot: the installer's buttons have names.
  var w = se.applicationProcesses.byName(win.proc).windows[win.idx];
  var places = [w];
  try { var sheets = w.sheets(); for (var i = 0; i < sheets.length; i++) places.push(sheets[i]); } catch (e) {}
  for (var k = 0; k < places.length; k++) {
    try { var b = places[k].buttons.whose({name: name}); if (b.length) { b[0].click(); return true; } } catch (e) {}
    try {
      var groups = places[k].groups();
      for (var g = 0; g < groups.length; g++) {
        var gb = groups[g].buttons.whose({name: name});
        if (gb.length) { gb[0].click(); return true; }
      }
    } catch (e) {}
  }
  return false;
}
var INT = /^[+-]?\d+$/;
function click(f) {
  // Inputs are checked before the window is looked up, so a bad operand never
  // reaches osascript: a flag with no operand parses as `true`, and parseInt
  // turns "12px" into 12.
  if (!f.button && (!INT.test(String(f.x)) || !INT.test(String(f.y)))) {
    die('NO_COORDS', '--button NAME, or --x and --y as whole numbers, is required for click');
  }
  var win = resolve(f.title);
  focus(win);
  if (f.button) {
    if (!clickByName(win, f.button)) die('NO_SUCH_BUTTON', 'no button named "' + f.button + '" in "' + win.title + '" (looked in the window, its sheets, and their groups)');
    out('CLICKED button "' + f.button + '"');
  } else {
    if (!$.CGPreflightPostEventAccess()) die('NO_ACCESSIBILITY', 'This app may not post mouse events. Run: screenctl.js request');
    var x = parseInt(f.x, 10), y = parseInt(f.y, 10);
    // AppleScript's `click at` through a shell, because the JXA form of this one
    // command has no direct parameter and is refused on current macOS.
    var r = sh("/usr/bin/osascript -e 'tell application \"System Events\" to click at {" + x + ', ' + y + "}'");
    if (r === null) die('CLICK_FAILED', 'System Events refused the click. Run: screenctl.js request');
    out('CLICKED ' + x + ',' + y);
  }
  out('Screenshot again before the next click. Any click can move the layout.');
}
var KEYCODES = {enter: 36, 'return': 36, esc: 53, escape: 53, tab: 48, space: 49, 'delete': 51,
                backspace: 51, up: 126, down: 125, left: 123, right: 124};
var MODS = {cmd: 'command', command: 'command', ctrl: 'control', control: 'control',
            shift: 'shift', alt: 'option', option: 'option'};
function key(f) {
  if (!f.keys) die('NO_KEYS', '--keys is required, e.g. enter, esc, cmd+v');
  var win = resolve(f.title);
  focus(win);
  var using = [], rest = [];
  String(f.keys).toLowerCase().split('+').forEach(function (p) { if (MODS[p]) using.push(MODS[p] + ' down'); else if (p) rest.push(p); });
  if (rest.length !== 1) die('BAD_KEY', 'expected exactly one non-modifier key in "' + f.keys + '"');
  var opts = using.length ? {using: using} : {};
  try {
    if (KEYCODES[rest[0]] !== undefined) se.keyCode(KEYCODES[rest[0]], opts); else se.keystroke(rest[0], opts);
  } catch (e) { die('SEND_FAILED', 'System Events refused the keystroke (' + e.message + '). Run: screenctl.js request'); }
  delay(0.3);
  out('SENT: ' + f.keys);
}
function request() {
  out(OWNER);
  // Each call shows the system prompt once and adds the right app to the list in
  // System Settings, switched off, ready to toggle.
  var ax;
  try { ax = $.AXIsProcessTrustedWithOptions($({'AXTrustedCheckOptionPrompt': true})); }
  catch (e) { ax = $.AXIsProcessTrusted(); }
  var post = $.CGRequestPostEventAccess();
  var rec = $.CGRequestScreenCaptureAccess();
  out('accessibility: ' + ((ax && post) ? 'ok' : 'REQUESTED'));
  out('screen_recording: ' + (rec ? 'ok' : 'REQUESTED'));
  if (!(ax && post)) sh('/usr/bin/open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"');
  else if (!rec) sh('/usr/bin/open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"');
  out('Tell the person: in System Settings, switch on Claude Code in Accessibility and in Screen Recording.');
}
function doctor() {
  out('os:      Darwin ' + (sh('/usr/bin/sw_vers -productVersion') || ''));
  out('driver:  screenctl.js (before python3 exists); use screenctl.py once python3 runs');
  out(OWNER);
  var ok = true;
  var post = $.CGPreflightPostEventAccess();
  out('post_events: ' + (post ? 'ok' : 'DENIED - run `screenctl.js request`, then switch Claude Code on in System Settings > Privacy & Security > Accessibility'));
  ok = ok && post;
  var rec = $.CGPreflightScreenCaptureAccess();
  out('screen_recording: ' + (rec ? 'ok' : 'DENIED - run `screenctl.js request`, then switch Claude Code on in System Settings > Privacy & Security > Screen Recording'));
  ok = ok && rec;
  var state = systemEventsState();
  out('accessibility: ' + (state === 'ok' ? 'ok'
      : state === 'automation' ? 'AUTOMATION_DENIED - ' + AUTOMATION_HELP
      : 'DENIED - run `screenctl.js request`, then switch Claude Code on in System Settings > Privacy & Security > Accessibility'));
  ok = ok && state === 'ok';
  var n = 0;
  try { n = listWindows().length; } catch (e) {}
  out('windows_visible: ' + n);
  ok = ok && n > 0;
  out(ok ? 'DOCTOR_OK' : 'DOCTOR_PROBLEMS - fix the lines above before driving');
  if (!ok) $.exit(1);
}
function handback(f) {
  var text = f.text || 'Done. Your computer is yours again.';
  var forward = false;
  if (!f.quiet) {
    // `open` activates through LaunchServices: no Accessibility needed, so the
    // hand-back works even when driving has broken.
    sh('/usr/bin/open -b ' + CLAUDE_BUNDLE_ID + ' || /usr/bin/open -a Claude');
    for (var i = 0; i < 15; i++) { delay(0.2); if (frontProc() === 'Claude') { forward = true; break; } }
  }
  sh('/usr/bin/afplay /System/Library/Sounds/Glass.aiff >/dev/null 2>&1 &');
  var notified = true;
  try { app.displayNotification(text, {withTitle: 'Claude'}); } catch (e) { notified = false; }
  out('HANDED_BACK');
  out(f.quiet ? 'claude_in_front: left alone (--quiet)'
              : 'claude_in_front: ' + (forward ? 'yes' : 'NO - say in the chat that they should switch back to Claude'));
  out('notified: ' + (notified ? 'yes' : 'no'));
}

function run(argv) {
  var a = parse(argv);
  if (!a.cmd || a.cmd === '--help' || a.cmd === '-h') { usage(); return; }
  if (COMMANDS.indexOf(a.cmd) < 0) { usage(); die('BAD_COMMAND', 'unknown command "' + a.cmd + '"'); }
  ({doctor: doctor, request: request, shot: shot, click: click, key: key, handback: handback})[a.cmd](a.flags);
}
