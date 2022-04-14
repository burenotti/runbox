#include <iostream>

using namespace std;


int main() {
    int number;
    int div = 2;
    cin >> number;
    while (number > 1) {
        if (number % div == 0) {
            number /= div;
            cout << div << " ";
        } else {
            ++div;
        }
    }
}