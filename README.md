# Purpose of the project
The aim of this project is to create an automatic exam corrector application for TOEIC.

___
## Structure of the project (UI)
When the application starts, it is possible for the user to create or open existing projects.  
An existing project is composed of a csv file having the 200 good answers of the chosen exam by the user. The user  can add a group of users (pdf) or just a user (pdf or image : jpg/png).
If the user choses to create a project he can just add an existing csv file (for example to have a project for another class with the same exam) or create a csv from the app.  
It is possible to see the result result of a unique copy (raw score or estimated TOEIC score by cross-product) AND by group with the average score, etc. with the possibility to export the stats to EXCEL.

___
## How to run the project

### ASSISTED INSTALLATION (macOS/Linux)
Python 3.11 is required. It can be easily downloaded from https://www.python.org/downloads/   
MacOS and Linux only.

#### Linux Users:
- Rename install.command → install.sh and run.command → run.sh

then, on command line:
- ```./install.sh ```-> to install all dependencies including Python3.11 if you don't have.
- ```./run.sh -> ``` to run the app (python3.11 only)

#### MACOS Users:
Simply double-click install.command, then run.command.

On some systems, you may need to make the files executable:  
```chmod +x install.command run.command```

Additionally, macOS Gatekeeper may flag the scripts as suspicious : this is expected and safe.

### MANUAL INSTALLATION (Windows & Others)
Tested on 3.11.9.

- ``` python -m pip install deps.txt```
- ``` python ./main.py ```