#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IOS="$ROOT/ios"
FRONTEND="$ROOT/frontend"
BUILD="$IOS/build"
DERIVED="$BUILD/Derived"
APP="$DERIVED/Build/Products/Release-iphoneos/Plove.app"
STAGE="$BUILD/package"
OUT="$IOS/releases/Plove_4.0.0_build2_iOS15-27_TrollStore_unsigned.ipa"
NODEBIN="/Users/plove/.nvm/versions/node/v22.22.0/bin"
export PATH="$NODEBIN:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin"

cd "$FRONTEND"
npm run typecheck
npm run build

rm -rf "$DERIVED"
xcodebuild   -project "$IOS/Plove4.xcodeproj"   -scheme Plove   -configuration Release   -sdk iphoneos   -derivedDataPath "$DERIVED"   CODE_SIGNING_ALLOWED=NO   CODE_SIGNING_REQUIRED=NO   CODE_SIGN_IDENTITY=""   build | tee "$IOS/build-xcode.log"

test -x "$APP/Plove"
rm -rf "$APP/WebApp"
mkdir -p "$APP/WebApp"
cp -R "$FRONTEND/dist/." "$APP/WebApp/"

rm -rf "$STAGE"
mkdir -p "$STAGE/Payload"
cp -R "$APP" "$STAGE/Payload/Plove.app"

mkdir -p "$IOS/releases"
rm -f "$OUT"
cd "$STAGE"
/usr/bin/zip -qry "$OUT" Payload

/usr/bin/unzip -t "$OUT" >/dev/null
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$STAGE/Payload/Plove.app/Info.plist"
/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$STAGE/Payload/Plove.app/Info.plist"
echo "$OUT"
