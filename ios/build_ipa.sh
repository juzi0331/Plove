#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
IOS="$ROOT/ios"
FRONTEND="$ROOT/frontend"
BUILD="$IOS/build"
APP="$BUILD/Derived/Build/Products/Release-iphoneos/Plove.app"
VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$IOS/App/Info.plist")
BUILD_NO=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$IOS/App/Info.plist")
OUT="$IOS/releases/Plove_${VERSION}_build${BUILD_NO}_iOS15-27_TrollStore_unsigned.ipa"

export PATH="/Users/plove/.nvm/versions/node/v22.22.0/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin"

cd "$FRONTEND"
if [ ! -d node_modules ]; then
  npm ci
fi
npm run typecheck
npm run build

cd "$ROOT"
rm -rf "$BUILD"
mkdir -p "$IOS/releases"

xcodebuild   -project "$IOS/Plove4.xcodeproj"   -scheme Plove   -configuration Release   -sdk iphoneos   -derivedDataPath "$BUILD/Derived"   CODE_SIGNING_ALLOWED=NO   CODE_SIGNING_REQUIRED=NO   build

test -d "$APP"
rm -rf "$APP/WebApp"
mkdir -p "$APP/WebApp"
/usr/bin/ditto "$FRONTEND/dist/" "$APP/WebApp/"

rm -rf "$BUILD/Payload"
mkdir -p "$BUILD/Payload"
/usr/bin/ditto "$APP" "$BUILD/Payload/Plove.app"
rm -f "$OUT"
(
  cd "$BUILD"
  /usr/bin/zip -qry "$OUT" Payload
)

test -f "$OUT"
/usr/bin/unzip -t "$OUT" >/dev/null
echo "IPA: $OUT"
shasum -a 256 "$OUT"
