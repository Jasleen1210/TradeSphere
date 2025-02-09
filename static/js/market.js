let currentPrice = 0; // Store price for selected card

function showPopup(price) {
    currentPrice = price; // Set the fixed price based on the clicked card
    document.getElementById("popup").style.display = "flex";
}

function closePopup() {
    document.getElementById("popup").style.display = "none";
}

function updatePrice() {
    let quantity = document.getElementById("quantity").value;
    let finalPrice = quantity * currentPrice;
    document.getElementById("final-price").innerText = finalPrice || 0;
}

function submitRequest() {
    closePopup(); // Close the buy popup

    // Show success message
    document.getElementById("success-popup").style.display = "flex";

    // Automatically close success popup after a second
    setTimeout(() => {
        document.getElementById("success-popup").style.display = "none";
    }, 1000);
}
