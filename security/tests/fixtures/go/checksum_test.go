package fixture

import "testing"

func TestChecksum(t *testing.T) {
	if got := Checksum([]byte("abc")); got != "900150983cd24fb0d6963f7d28e17f72" {
		t.Fatalf("Checksum(abc) = %s", got)
	}
}
