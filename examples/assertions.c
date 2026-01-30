#include <assert.h>

int main(void)
{
  int a[] = {0, 1, 2, 3};
  __CPROVER_assert(a[3] != 3, "expected failure: last element is 3");
  return 0;
}
