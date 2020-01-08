function generateLayer() {
    function downloadObjectAsJson(data){
        let exportName = 'layer';
        let dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
        let downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", exportName + ".json");
        document.body.appendChild(downloadAnchorNode); // required for firefox
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    }

    let selectionAdversaryID = $('#layer-selection-adversary option:selected').attr('value');
    let postData = selectionAdversaryID ? {'index':'adversary', 'adversary_id': selectionAdversaryID} : {'index': 'all'};
    restRequest('POST', postData, downloadObjectAsJson, '/plugin/compass/layer');
}

function uploadAdversaryLayerButtonFileUpload() {
    document.getElementById('adversaryLayerInput').click();
}
$('#adversaryLayerInput').on('change', function (event){
    if(event.currentTarget) {
        let filename = event.currentTarget.files[0].name;
        if(filename){
            uploadAdversaryLayer();
        }
    }
});

function uploadAdversaryLayer() {
    let file = document.getElementById('adversaryLayerInput').files[0];
    let fd = new FormData();
    fd.append('file', file);
    $.ajax({
         type: 'POST',
         url: '/plugin/compass/adversary',
         data: fd,
         processData: false,
         contentType: false
    }).done(function (){
        alert('New Adversary Created.');
    })
}

function openHelp() {
    document.getElementById("duk-modal-compass").style.display="block";
}