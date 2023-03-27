# topo-order-commits
Implementation will search for `.git` directory and perform a deterministic topological sort of the commits reachable from any
branch heads found and perform any relevant error-handling.

Here is an example:

```
  c0 -> c1 -> c2 (branch-1)
         \
          c3 -> c4 (branch-2, branch-5)
                 \
            c5 -> c6 (branch-3) -> c7
```

Graph considered (reachable from branches only):

```
  c0 -> c1 -> c2 (branch-1)
         \
          c3 -> c4 (branch-2, branch-5)
                 \
            c5 -> c6 (branch-3)
```

Valid topological order (same in subsequent calls):

(c6, c5, c4, c3, c2, c1, c0)
Valid sticky graph (# indicate my comment:

```
c6 branch-3
c5
= # c5 has no parents

=c6 # c6 is the sole child of c4
c4 branch-2 branch-5
c3
c1= # c1 is parent of c3

= # c2 has no children
c2 branch-1
c1
c0
```

Relevant assignment can be found [here](https://web.cs.ucla.edu/classes/winter23/cs35L/assign/assign6.html).
