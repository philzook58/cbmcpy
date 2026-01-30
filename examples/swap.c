int swap(int *src, int *dst) {
    int tmp = *src;
    *src = *dst;
    *dst = tmp;
    return 0;
}

int main() {
    int x = 1;
    int y = 2;
    swap(&x, &x);
    __CPROVER_assert(x == 2, "swap should fail under aliasing");
    return 0;
}
