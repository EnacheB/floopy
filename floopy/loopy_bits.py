"""
MIT License

Copyright (c) 2018 Andreas Klöckner and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""



import loopy as lp
import numpy as np
import collections
import six

def natorder(key):
    # Return natural ordering for strings, as opposed to dictionary order.
    # E.g. will result in
    #  'abc1' < 'abc9' < 'abc10'
    # rather than
    #  'abc1' < 'abc10' < 'abc9'
    # Based on
    # http://code.activestate.com/recipes/285264-natural-string-sorting/#c7
    import re
    return [int(n) if n else s for n, s in re.findall(r'(\d+)|(\D+)', key)]

def natsorted(seq, key=lambda x: x):
    return sorted(seq, key=lambda y: natorder(key(y)))

def knl_to_json(knl, what=None, with_dependencies=False, use_separators=True):
        if knl == None:
            return None
        all_what = set([
            "name",
            "arguments",
            "domains",
            "tags",
            "variables",
            "rules",
            "instructions",
            "Dependencies",
            "schedule",
            ])

        first_letter_to_what = dict(
                (w[0], w) for w in all_what)
        assert len(first_letter_to_what) == len(all_what)

        if what is None:
            what = all_what.copy()
            if not with_dependencies:
                what.remove("Dependencies")

        if isinstance(what, str):
            if "," in what:
                what = what.split(",")
                what = set(s.strip() for s in what)
            else:
                what = set(
                        first_letter_to_what[w]
                        for w in what)

        if not (what <= all_what):
            raise LoopyError("invalid 'what' passed: %s"
                    % ", ".join(what-all_what))

        lines = {}

        kernel = knl

        if "name" in what:
            lines['p_name'] = kernel.name

        if "arguments" in what:
            lines['p_arguments'] = []
            for arg_name in natsorted(kernel.arg_dict):
                if isinstance(kernel.arg_dict[arg_name],lp.ValueArg):
                    typ = "value"
                elif kernel.arg_dict[arg_name].address_space == lp.AddressSpace.GLOBAL:
                    typ = "global"
                lines['p_arguments'].append([arg_name, str(kernel.arg_dict[arg_name]), typ])

        if "domains" in what:
            lines['p_domains'] = []
            for dom, parents in zip(kernel.domains, kernel.all_parents_per_domain()):
                lines['p_domains'].append(len(parents)*"  " + str(dom))

        if "tags" in what:
            lines['p_tags'] = []
            for iname in natsorted(kernel.all_inames()):
                tags = kernel.iname_to_tag.get(iname,frozenset())
                if not tags:
                    lines['p_tags'].append((str(iname), [] ))
                else:
                    if not isinstance(tags, collections.Iterable):
                        tags = [tags,]
                    lines['p_tags'].append((str(iname), [str(t) for t in tags] ))

        if "variables" in what and kernel.temporary_variables:
            lines['p_variables'] = []
            for tv in natsorted(six.itervalues(kernel.temporary_variables),
                    key=lambda tv: tv.name):
                lines['p_variables'].append(str(tv))

        if "rules" in what and kernel.substitutions:
            lines['p_rules'] = []
            for rule_name in natsorted(six.iterkeys(kernel.substitutions)):
                lines['p_rules'].append((rule_name, str(kernel.substitutions[rule_name])))

        if "instructions" in what:
            lines['p_instructions'] = []
            loop_list_width = 35

            # {{{ topological sort

            printed_insn_ids = set()
            printed_insn_order = []

            def insert_insn_into_order(insn):
                if insn.id in printed_insn_ids:
                    return
                printed_insn_ids.add(insn.id)

                for dep_id in natsorted(insn.depends_on):
                    insert_insn_into_order(kernel.id_to_insn[dep_id])

                printed_insn_order.append(insn)

            for insn in kernel.instructions:
                insert_insn_into_order(insn)

            # }}}


            Fore = kernel.options._fore  # noqa
            Style = kernel.options._style  # noqa

            from loopy.kernel.tools import draw_dependencies_as_unicode_arrows
            deps = draw_dependencies_as_unicode_arrows(
                        printed_insn_order, fore=Fore, style=Style)
            if not isinstance(deps, list):
                deps = [deps]

            for insn, (arrows, extender) in zip(
                    printed_insn_order, deps):

                if isinstance(insn, lp.MultiAssignmentBase):
                    lhs = ", ".join(str(a) for a in insn.assignees)
                    rhs = str(insn.expression)
                    trailing = []
                elif isinstance(insn, lp.CInstruction):
                    lhs = ", ".join(str(a) for a in insn.assignees)
                    rhs = "CODE(%s|%s)" % (
                            ", ".join(str(x) for x in insn.read_variables),
                            ", ".join("%s=%s" % (name, expr)
                                for name, expr in insn.iname_exprs))

                    trailing = ["    "+l for l in insn.code.split("\n")]
                elif isinstance(insn, lp.BarrierInstruction):
                    lhs = ""
                    rhs = "... %sbarrier" % insn.kind[0]
                    trailing = []

                elif isinstance(insn, lp.NoOpInstruction):
                    lhs = ""
                    rhs = "... nop"
                    trailing = []

                else:
                    raise LoopyError("unexpected instruction type: %s"
                            % type(insn).__name__)

                order = kernel._get_iname_order_for_printing()
                loop_list = ",".join(
                    sorted(kernel.insn_inames(insn), key=lambda iname: order[iname]))

                options = [Fore.GREEN+insn.id+Style.RESET_ALL]
                if insn.priority:
                    options.append("priority=%d" % insn.priority)
                if insn.tags:
                    options.append("tags=%s" % ":".join(insn.tags))
                if isinstance(insn, lp.Assignment) and insn.atomicity:
                    options.append("atomic=%s" % ":".join(
                        str(a) for a in insn.atomicity))
                if insn.groups:
                    options.append("groups=%s" % ":".join(insn.groups))
                if insn.conflicts_with_groups:
                    options.append(
                            "conflicts=%s" % ":".join(insn.conflicts_with_groups))
                if insn.no_sync_with:
                    options.append("no_sync_with=%s" % ":".join(
                        "%s@%s" % entry for entry in sorted(insn.no_sync_with)))

                if lhs:
                    core = "%s <- %s" % (
                        Fore.CYAN+lhs+Style.RESET_ALL,
                        Fore.MAGENTA+rhs+Style.RESET_ALL,
                        )
                else:
                    core = Fore.MAGENTA+rhs+Style.RESET_ALL

                if len(loop_list) > loop_list_width:
                    lines['p_instructions'].append("%s [%s]" % (arrows, loop_list))
                    lines['p_instructions'].append("%s %s%s   # %s" % (
                        extender,
                        (loop_list_width+2)*" ",
                        core,
                        ", ".join(options)))
                else:
                    lines['p_instructions'].append("%s [%s]%s%s   # %s" % (
                        arrows,
                        loop_list, " "*(loop_list_width-len(loop_list)),
                        core,
                        ",".join(options)))

                lines['p_instructions'].extend(trailing)

                if insn.predicates:
                    lines['p_instructions'].append(10*" " + "if (%s)" % " && ".join(
                        [str(x) for x in insn.predicates]))


        dep_lines = []
        for insn in kernel.instructions:
            if insn.depends_on:
                dep_lines.append("%s : %s" % (insn.id, ",".join(insn.depends_on)))

        if "Dependencies" in what and dep_lines:

            lines['p_dependencies'] = dep_lines

        if "schedule" in what and kernel.schedule is not None:
            from loopy.schedule import dump_schedule
            lines['p_schedule'] = dump_schedule(kernel, kernel.schedule)


        return lines
