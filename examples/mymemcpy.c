void mymemcpy(char *dest, const char *src, int n) {
    for (int i = 0; i < n; i++) {
        dest[i] = src[i];
    }
}