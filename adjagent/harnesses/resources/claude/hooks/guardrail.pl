#!/usr/bin/env perl
# !INSTALLED! from adjagent/harnesses/resources/ — do not edit here: request changes from the adjagent project
#
# Claude Code PreToolUse hook for Bash.
# Prevents in-place edits using shell tools, redirects model to use the Edit and Write tools.
#
# Exit 2 blocks the call; any other non-zero exit is reported as a hook error and does not block.
# Perl's own exit on a failed `use` or an uncaught `die` can be 2, so every module is loaded with
# `require` and the whole body runs inside one `eval` that exits 1 on any failure.

use strict;
use warnings;

# Scratch trees a command may write into without the edit tools.
my @scratch = ('.claude-temp', 'test-data/transient');

# resolve joins root and p lexically, as node's path.resolve does: the filesystem is never read.
sub resolve {
  my ($root, $p) = @_;
  my @out;
  for my $seg (split m{/}, "${root}/${p}") {
    next if $seg eq '' || $seg eq '.';
    if ($seg eq '..') {
      pop @out;
      next;
    }
    push @out, $seg;
  }
  return '/' . join('/', @out);
}

sub path_of {
  my ($word, $cwd) = @_;
  (my $p = $word) =~ s/^["']|["']\z//g;
  return resolve($p =~ m{^/} ? '' : $cwd, $p);
}

sub in_scratch {
  my ($abs, $root) = @_;
  for my $dir (@scratch) {
    my $base = resolve($root, $dir);
    return 1 if $abs eq $base || index($abs, "${base}/") == 0;
  }
  return 0;
}

# free is whether a target is a device, a descriptor duplication (2>&1), or scratch.
sub free {
  my ($word, $cwd, $root) = @_;
  return 1 if $word eq '' || $word =~ /^&/ || $word eq '-';
  my $abs = path_of($word, $cwd);
  return index($abs, '/dev/') == 0 || in_scratch($abs, $root);
}

# redirects reads each >, >>, >|, >! and >&file target, skipping heredoc bodies,
# which are not shell. A quoted span is matched whole, so a > inside it is never
# examined, and the [^>=-] before an operator skips -> and =>. A >& before a
# digit or - duplicates or closes a descriptor and writes nothing.
sub redirects {
  my ($cmd) = @_;
  $cmd =~ s/((?<!<)<<-?\s*(["']?)(\w+)\2[^\n]*).*?(?:\n[ \t]*\3(?=\n|\z)|\z)/$1/gs;
  my @out;
  while ($cmd =~ /"([^"]*)"|'([^']*)'|(?:^|[^>=-])>(?:>|&(?![\d-]))?[|!]?\s*(?:"([^"]*)"|'([^']*)'|([^\s;&|<>]+))/g) {
    my $target = $3 // $4 // $5;
    push @out, $target if defined $target && $target ne '';
  }
  return @out;
}

my $in_place = qr/\b(?:g?sed|perl|ruby)\b[^\n;&|]*\s(?:-[a-zA-Z0-9]*ie?\b|--in-place\b)/;
my $script = qr/\b(?:python[0-9.]*|ruby|perl|node)\b[^\n]*(?:\s-(?:c|e)\b|<<-?\s*['"]?\w+)/;
my $writes = qr/(?:open\s*\([^)]*['"][wa]b?\+?['"]|(?:writeFile|appendFile)(?:Sync)?\s*\(|createWriteStream\s*\(|(?<!stdout)(?<!stderr)\.write\s*\(|\.write_(?:text|bytes)\s*\()/;

# mutation names the first form that would change a file behind the edit
# tools' back, or undef where the command is free of them. Relative targets
# resolve against cwd, scratch trees against root.
sub mutation {
  my ($cmd, $cwd, $root) = @_;
  (my $unquoted = $cmd) =~ s/"[^"]*"|'[^']*'/ /g;
  return 'an in-place sed, perl or ruby edit' if $unquoted =~ $in_place;
  for my $target (redirects($cmd)) {
    return "a redirect that writes ${target}" if !free($target, $cwd, $root);
  }
  for my $part (split /(?:&&|\|\||;|\||\n)/, $cmd) {
    (my $trimmed = $part) =~ s/^\s+|\s+\z//g;
    my @ws = grep { $_ ne '' } split /\s+/, $trimmed;
    (my $name = $ws[0] // '') =~ s{.*/}{}s;
    if ($name eq 'tee') {
      for my $word (@ws[1 .. $#ws]) {
        return "tee writing ${word}" if $word !~ /^-/ && !free($word, $cwd, $root);
      }
    }
    if ($name eq 'cp' || $name eq 'mv') {
      my @args = grep { !/^-/ } @ws[1 .. $#ws];
      my $dest = pop @args;
      next if !defined $dest;
      my $abs = path_of($dest, $cwd);
      my @hit = -d $abs ? map { "${abs}/" . (path_of($_, $cwd) =~ s{.*/}{}r) } @args : ($abs);
      return "${name} overwriting ${dest}" if !in_scratch($abs, $root) && grep { -f } @hit;
    }
  }
  return 'an inline script that writes a file' if $cmd =~ $script && $cmd =~ $writes;
  return undef;
}

my $reason;
my $ok = eval {
  binmode STDERR, ':utf8';
  require JSON::PP;
  my $input = JSON::PP->new->utf8->decode(do { local $/; <STDIN> });
  if (($input->{tool_name} // '') eq 'Bash') {
    my $root = $ENV{CLAUDE_PROJECT_DIR} || $input->{cwd};
    die "no project root: CLAUDE_PROJECT_DIR is unset and the input carries no cwd\n" if !$root;
    $reason = mutation($input->{tool_input}{command} // '', $input->{cwd} || $root, $root);
  }
  1;
};
if (!$ok) {
  print STDERR 'guardrail: ', $@;
  exit 1;
}
if (defined $reason) {
  print STDERR "Blocked: ${reason}. Use the Edit and Write tools for file changes; command output and other scratch belongs under .claude-temp/.\n";
  exit 2;
}
exit 0;
