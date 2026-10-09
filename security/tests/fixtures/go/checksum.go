// Package fixture is a self-test target for the Go workflow.
package fixture

import (
	"crypto/md5" // CANARY: weak hash, which Semgrep's p/golang and gosec rules must flag
	"encoding/hex"
)

// Checksum returns the hex MD5 of data.
func Checksum(data []byte) string {
	sum := md5.Sum(data)
	return hex.EncodeToString(sum[:])
}
