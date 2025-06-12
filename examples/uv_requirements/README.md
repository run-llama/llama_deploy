Run from the root directory (to avoid uv environment ambiguity)

```sh
uv run llamactl serve examples/uv_requirements/deployment.yaml
```

Test with:

```sh
llamactl run --deployment uv --arg message 'Hello from UV!'
```

Should output art from a pip and a uv dependency:
```
    __  __     ____         ____                        __  ___    ____
   / / / /__  / / /___     / __/________  ____ ___     / / / / |  / / /
  / /_/ / _ \/ / / __ \   / /_/ ___/ __ \/ __ `__ \   / / / /| | / / /
 / __  /  __/ / / /_/ /  / __/ /  / /_/ / / / / / /  / /_/ / | |/ /_/
/_/ /_/\___/_/_/\____/  /_/ /_/   \____/_/ /_/ /_/   \____/  |___(_)

 ________________
< Hello from UV! >
 ----------------
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
