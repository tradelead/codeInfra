#!/usr/bin/env node
const cmd = process.argv[2];
const argv = require('minimist')(process.argv.slice(3));
require(`./cmd/${cmd}`)(argv)
  .catch((e) => {
    console.log('ERROR:', e.message);
    process.exit(1);
  });
