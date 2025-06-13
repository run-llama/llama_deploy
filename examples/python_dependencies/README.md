# `pyproject.toml` Dependencies

This example demonstrates different mechanisms for installing python dependencies

- python version ranges
- PEP 631 Dependency specification in pyproject.toml
- requirements.txt format


To run it

```sh
llamactl serve examples/python_dependencies/deployment.yaml
```

Then, you can test with:

```sh
llamactl run --deployment dependencies --arg message 'LlamaDeploy' --arg font swan
```

This should output some art from each dependency: `pyfiglet`, `cowpy`, and `python-fortune`
```

.    .                   .--.           .
|    |                   |   :          |
|    | .-.  .--.--. .-.  |   | .-. .,-. | .-. .  .
|    |(   ) |  |  |(   ) |   ;(.-' |   )|(   )|  |
'---'`-`-'`-'  '  `-`-'`-'--'  `--'|`-' `-`-' `--|
                                   |             ;
                                   '          `-'
 _________________________________________
/ Humpty Dumpty sat on the wall,          \
| Humpty Dumpty had a great fall!         |
| All the king's horses,                  |
| And all the king's men,                 |
\ Had scrambled eggs for breakfast again! /
 -----------------------------------------
\                             .       .
 \                           / `.   .' "
  \                  .---.  <    > <    >  .---.
   \                 |    \  \ - ~ ~ - /  /    |
         _____          ..-~             ~-..-~
        |     |   \~~~\.'                    `./~~~/
       ---------   \__/                        \__/
      .'  O    \     /               /       \  "
     (_____,    `._.'               |         }  \/~~~/
      `----.          /       }     |        /    \__/
            `-.      |       /      |       /      `. ,~~|
                ~-.__|      /_ - ~ ^|      /- _      `..-'
                     |     /        |     /     ~-.     `-. _  _  _
                     |_____|        |_____|         ~ - . _ _ _ _ _>
```
