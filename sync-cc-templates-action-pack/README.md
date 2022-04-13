# Sync CC Templates and Action Bundles

- This tool can be used to synchronize change control templates and action bundles to another CVP cluster
- It is highly recommended for both cluster to run the same CVP Version
- It is highly recommended for the target cluster to not have any templates + action bundles 
- It is highly recommended to not create CC templates and actionbundles on the target cluster after the sync if 
  the sync will be reused to in the future to avoid potential UUID overlap and other issues
- DISCLAIMER: This is not an officially supported Arista product, use it at your own risk!