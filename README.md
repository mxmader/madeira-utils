# Madeira Utilities

This is a collection of functionality aimed to complement `madeira` with general purpose deployment utilities.

Functionality contained here may pertain to other platforms outside AWS, or provide wrappers for alternative services
for cost-saving, efficiency, performance, or other measures.

This package shall stand alone with respect to `madeira` (it shall have no direct dependencies on it).

## Scripts

* Packaging 3rd party dependencies for use as AWS lambda function layers:
```
package_layer.sh <package name> <version>
```
* Script executed inside the packaging container to gather the bits for the function layer:
```
create_layer.sh
```
* Sourceable function library with general-purpose app workflow utilities
```
shell_funcs.src
```
    Functions:
    * `madeira_run_dev <app>` - opens XFCE4 terminal with 2 tabs - each for API and UI container runtime + logging