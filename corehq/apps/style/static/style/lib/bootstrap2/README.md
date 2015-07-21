The reason why this bootstrap2 folder of boostrap.js exists instead of pulling
direct from the bootstrap2 submodule (/style/lib/bootstrap) is that make_hq_style
places it in here after merging additional plugins that we've created to support
custom components in hq that are bootstrap based.
