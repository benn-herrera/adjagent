#!/usr/bin/env perl
# !INSTALLED! from adjagent/harnesses/resources/ — do not edit here: request changes from the adjagent project
#
# Claude Code PreToolUse hook for Bash and the file tools.
# Prevents in-place edits using shell tools, redirects model to use the Edit and Write tools.
# On a kb install, also keeps every call out of kb-root/.index/, which kbase's own tools own.
#
# Exit 2 blocks the call; any other non-zero exit is reported as a hook error and does not block.
# Perl's own exit on a failed `use` or an uncaught `die` can be 2, so every module is loaded with
# `require` and the whole body runs inside one `eval` that exits 1 on any failure.

use strict;
use warnings;

# Scratch trees a command may write into without the edit tools.
my @scratch = ('.claude-temp', 'test-data/transient');

# A kb install's signal, the kbase skill in this script's own harness directory: never the root or
# the working directory, which --subdir makes wrong.
(my $kb_signal = $0) =~ s{[^/]*/[^/]*\z}{skills/kbase/SKILL.md};

# kbase's records, in <root>/kb-root/.index/.
my @kb_records = ('nodes.yaml', 'edges.yaml', 'format.yaml');
my $index_path = "kb-root/.index/ holds kbase's records: read them with kbase's `query` tool and change them with its `write` tool";
my $index_search = "${index_path}; exclude .index from this search (grep: --exclude-dir=.index; rg: -g '!**/.index/**'; find: -path '*/.index' -prune; Grep: a glob (opencode: include) no .index file matches; Glob: a pattern no .index file matches)";
my $excludes_index = qr/--exclude-dir[= ]['"]?\.index\b|(?:^|\s)(?:-g|--glob)[= ]['"]?!['"]?[^\s'"]*\.index|-(?:path|name)\s+['"]?[^\s'"]*\.index['"]?\s+-prune/;

# Claude's file tools that name one path, and the argument holding it.
my %path_arg = (Read => 'file_path', Write => 'file_path', Edit => 'file_path', NotebookEdit => 'notebook_path');

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

# A heredoc's body, which is not shell; substituting $1 keeps its command line.
my $heredoc_body = qr/((?<!<)<<-?\s*(["']?)(\w+)\2[^\n]*).*?(?:\n[ \t]*\3(?=\n|\z)|\z)/s;

# redirects reads each >, >>, >|, >! and >&file target, skipping heredoc bodies.
# A quoted span is matched whole, so a > inside it is never
# examined, and the [^>=-] before an operator skips -> and =>. A >& before a
# digit or - duplicates or closes a descriptor and writes nothing.
sub redirects {
  my ($cmd) = @_;
  $cmd =~ s/$heredoc_body/$1/g;
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

# real follows symlinks through the longest existing prefix of a lexically resolved path, so a path
# is judged where it lands; the part that does not exist stays as written.
sub real {
  my ($abs) = @_;
  my ($head, $tail) = ($abs, '');
  while ($head ne '' && !-e $head) {
    $head =~ s{/([^/]*)\z}{};
    $tail = "/$1$tail";
  }
  my $found = $head eq '' ? '' : Cwd::realpath($head) // $head;
  return $found eq '/' ? ($tail || '/') : "${found}${tail}";
}

sub under {
  my ($p, $dir) = @_;
  return $p eq $dir || index($p, "${dir}/") == 0;
}

# glob_re reads one path segment as a glob over *, ?, […] and {a,b}.
sub glob_re {
  my ($glob) = @_;
  my ($re, $depth) = ('', 0);
  for my $t ($glob =~ /\[[!^]?[^\]]+\]|[*?{},]|[^*?[{},]+|\[/g) {
    if ($t eq '*') { $re .= '.*' }
    elsif ($t eq '?') { $re .= '.' }
    elsif ($t eq '{') { $re .= '(?:'; $depth++ }
    elsif ($t eq '}' && $depth) { $re .= ')'; $depth-- }
    elsif ($t eq ',' && $depth) { $re .= '|' }
    elsif ($t =~ /^\[([!^]?)(.+)\]\z/s) { $re .= '[' . ($1 ? '^' : '') . $2 . ']' }
    else { $re .= quotemeta $t }
  }
  $re .= ')' x $depth;
  return qr/^(?:${re})\z/s;
}

# glob_root is a glob's leading literal segments, those before the first holding a glob character.
sub glob_root {
  my @lit;
  for my $seg (split m{/}, $_[0], -1) {
    last if $seg =~ /[*?[{]/;
    push @lit, $seg;
  }
  return join '/', @lit;
}

# search_reason judges a search rooted at base whose file filter is a glob, or undef for none: one
# rooted in kb-root/ is refused unless its filter cannot match a record.
sub search_reason {
  my ($base, $filter, $kb, $subject) = @_;
  return $index_path if under($base, $subject);
  return undef if !under($base, $kb);
  if (defined $filter && $filter ne '') {
    my $re = glob_re($filter =~ s{.*/}{}sr);
    return undef if !grep { $_ =~ $re } @kb_records;
  }
  return $index_search;
}

# shell_index_reason refuses a command with a word resolving into the subject, and a recursive
# search or walk rooted in kb-root/ that does not exclude .index. Existence checks pass.
sub shell_index_reason {
  my ($cmd, $cwd, $kb, $subject) = @_;
  for my $part (split /(?:&&|\|\||;|\||\n)/, $cmd =~ s/$heredoc_body/$1/gr) {
    my @ws = grep { $_ ne '' } split /\s+/, $part;
    my $name = ($ws[0] // '') =~ s{.*/}{}sr;
    next if $name eq 'stat' || ($name =~ /^(?:test|\[)\z/ && ($ws[1] // '') =~ /^-[edf]\z/);
    return $index_path if grep { under(real(path_of($_, $cwd)), $subject) } @ws;
    my @args = @ws[1 .. $#ws];
    my $recursive = $name =~ /^(?:rg|find|tree)\z/
      || ($name eq 'grep' && grep { /^-[a-zA-Z]*[rR]/ || /^--(?:dereference-)?recursive\z/ } @args)
      || ($name eq 'ls' && grep { /^-[a-zA-Z]*R/ || $_ eq '--recursive' } @args);
    next if !$recursive || $part =~ $excludes_index;
    return $index_search if grep { under(real(path_of($_, $cwd)), $kb) } '.', grep { !/^-/ } @args;
  }
  return undef;
}

# index_reason names why a call reaches into <root>/kb-root/.index/, or undef where it does not. A
# path collapses .. against cwd, then follows symlinks, as the root's own kb-root/ does.
sub index_reason {
  my ($tool, $in, $cwd, $root) = @_;
  my $kb = real(resolve($root, 'kb-root'));
  my $subject = real(resolve($root, 'kb-root/.index'));
  my $at = sub { real(path_of($_[0] // '', $cwd)) };
  if ($tool eq 'Bash') {
    return shell_index_reason($in->{command} // '', $cwd, $kb, $subject);
  }
  if (my $arg = $path_arg{$tool}) {
    return under($at->($in->{$arg}), $subject) ? $index_path : undef;
  }
  if ($tool eq 'Grep') {
    return search_reason($at->($in->{path}), $in->{glob}, $kb, $subject);
  }
  if ($tool eq 'Glob') {
    my $base = real(path_of(glob_root($in->{pattern} // ''), path_of($in->{path} // '', $cwd)));
    return search_reason($base, $in->{pattern}, $kb, $subject);
  }
  return undef;
}

my ($reason, $refusal);
my $ok = eval {
  binmode STDERR, ':utf8';
  require JSON::PP;
  my $input = JSON::PP->new->utf8->decode(do { local $/; <STDIN> });
  my $tool = $input->{tool_name} // '';
  my $kb_on = -e $kb_signal;
  if ($tool eq 'Bash' || $kb_on) {
    my $root = $ENV{CLAUDE_PROJECT_DIR} || $input->{cwd};
    die "no project root: CLAUDE_PROJECT_DIR is unset and the input carries no cwd\n" if !$root;
    my $cwd = $input->{cwd} || $root;
    my $in = $input->{tool_input} // {};
    if ($kb_on) {
      require Cwd;
      $refusal = index_reason($tool, $in, $cwd, $root);
    }
    $reason = mutation($in->{command} // '', $cwd, $root) if !defined $refusal && $tool eq 'Bash';
  }
  1;
};
if (!$ok) {
  print STDERR 'guardrail: ', $@;
  exit 1;
}
if (defined $refusal) {
  print STDERR "Blocked: ${refusal}\n";
  exit 2;
}
if (defined $reason) {
  print STDERR "Blocked: ${reason}. Use the Edit and Write tools for file changes; command output and other scratch belongs under .claude-temp/.\n";
  exit 2;
}
exit 0;
