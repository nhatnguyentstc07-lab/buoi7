// ======================= PHẦN 1: KIỂM TRA CHẴN/LẺ =======================

// Cách 1: Dùng if-else
function kiemTraChanLe1(n) {
    if (n % 2 === 0) {
        return "Chẵn";
    } else {
        return "Lẻ";
    }
}

// Cách 2: Dùng toán tử ternary (điều kiện)
function kiemTraChanLe2(n) {
    return n % 2 === 0 ? "Chẵn" : "Lẻ";
}

// Cách 3: Dùng switch-case (dùng biểu thức so sánh)
function kiemTraChanLe3(n) {
    switch (n % 2) {
        case 0:
            return "Chẵn";
        default:
            return "Lẻ";
    }
}

// ======================= PHẦN 2: KIỂM TRA SỐ NGUYÊN TỐ =======================

// Cách 1: Dùng vòng lặp for cơ bản
function laSoNguyenTo1(n) {
    if (n <= 1) return false;
    for (let i = 2; i < n; i++) {
        if (n % i === 0) return false;
    }
    return true;
}

// Cách 2: Dùng vòng lặp while và kiểm tra tối ưu (chỉ đến sqrt(n))
function laSoNguyenTo2(n) {
    if (n <= 1) return false;
    if (n === 2) return true;
    if (n % 2 === 0) return false;
    
    let i = 3;
    while (i <= Math.sqrt(n)) {
        if (n % i === 0) return false;
        i += 2;
    }
    return true;
}

// Cách 3: Dùng đệ quy
function laSoNguyenTo3(n, i = 2) {
    if (n <= 1) return false;
    if (i > Math.sqrt(n)) return true;
    if (n % i === 0) return false;
    return laSoNguyenTo3(n, i + 1);
}

// ======================= PHẦN 3: IN SỐ NGUYÊN TỐ TỪ 1 ĐẾN N =======================

// Cách 1: Dùng for và gọi hàm kiểm tra nguyên tố
function inSoNguyenTo1(n) {
    let result = [];
    for (let i = 2; i <= n; i++) {
        if (laSoNguyenTo1(i)) {
            result.push(i);
        }
    }
    return result;
}

// Cách 2: Dùng for...of (tạo mảng rồi lọc)
function inSoNguyenTo2(n) {
    let numbers = Array.from({ length: n - 1 }, (_, idx) => idx + 2); // từ 2 đến n
    let primes = [];
    for (let num of numbers) {
        if (laSoNguyenTo2(num)) {
            primes.push(num);
        }
    }
    return primes;
}

// Cách 3: Dùng while và hàm kiểm tra nguyên tố
function inSoNguyenTo3(n) {
    let primes = [];
    let i = 2;
    while (i <= n) {
        if (laSoNguyenTo3(i)) {
            primes.push(i);
        }
        i++;
    }
    return primes;
}

// ======================= NHẬP DỮ LIỆU TỪ BÀN PHÍM =======================
const readline = require('readline');
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

rl.question("Nhập một số n: ", (input) => {
    let n = parseInt(input);
    
    console.log("\n========== PHẦN 1: KIỂM TRA CHẴN/LẺ ==========");
    console.log(`Cách 1: ${kiemTraChanLe1(n)}`);
    console.log(`Cách 2: ${kiemTraChanLe2(n)}`);
    console.log(`Cách 3: ${kiemTraChanLe3(n)}`);
    
    console.log("\n========== PHẦN 2: KIỂM TRA SỐ NGUYÊN TỐ ==========");
    console.log(`Cách 1: ${laSoNguyenTo1(n)}`);
    console.log(`Cách 2: ${laSoNguyenTo2(n)}`);
    console.log(`Cách 3: ${laSoNguyenTo3(n)}`);
    
    console.log("\n========== PHẦN 3: IN SỐ NGUYÊN TỐ TỪ 1 ĐẾN n ==========");
    console.log(`Cách 1: ${inSoNguyenTo1(n).join(", ")}`);
    console.log(`Cách 2: ${inSoNguyenTo2(n).join(", ")}`);
    console.log(`Cách 3: ${inSoNguyenTo3(n).join(", ")}`);
    
    rl.close();
});

