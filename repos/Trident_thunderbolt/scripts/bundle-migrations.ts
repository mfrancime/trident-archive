import { bundleMigrations } from '../src/db/bundle-migrations'

bundleMigrations().then((count) => {
  console.log(`Bundled ${count} migrations`)
})