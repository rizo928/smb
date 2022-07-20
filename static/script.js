
function to_clipboard(theText) {
    navigator.clipboard
    .writeText(theText)
    .then(() => {
        // alert('Successfully copied to the clipboard');
        console.log('Successfully copied to the clipboardlipboard API available');
    })
    .catch(() => {
        alert("Exception thrown trying to copy to the clipboard.");
     });
}

function to_tech_search(baseurl) {
    var copyText = document.getElementById("findTechImageId");
    copyText.select();
    copyText.setSelectionRange(0, 99999);
    destination = baseurl+'&searchstr='+copyText.value
    console.log('Redirecting to: '+destination);
    // window.open(destination); OPEN IN A NEW TAB
    window.location = destination; // OPEN IN THE SAME TAB
}

function uploadimage(){ 

    console.log('upload image button pressed'); 
}