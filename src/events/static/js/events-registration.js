/**
 * Created by couture on 01/12/16.
 */
var $table = $('#table'),

    // $flex1_selection = $('#event-Flex-1'),
    // $flex2_selection = $('#event-Flex-2'),

    $blockConfirmModal = $('#block-confirmation-modal'),
    $blockConfirmModalTitle = $('#block-confirmation-modal').find('.modal-title'),
    $blockConfirmModalBody = $('#block-confirmation-modal').find('.modal-body'),
    $btnConfirmFlex1 = $('#btn-confirm-flex-1'),
    $btnConfirmFlex2 = $('#btn-confirm-flex-2');
    // $btnCancel = $('#btn-confirm-cancel');

// function getIdSelections() {
//     console.log("getting selections");
//     return $.map($table.bootstrapTable('getSelections'), function (row) {
//         return row.id
//     });
// }

// FLEX1ID = 1;
// FLEX2ID = 2;
F1_XOR_F2 = 0;
F1_OR_F2 = 1;
F1_AND_F2 = 2;
FLEX1 = "FLEX1"
FLEX2 = "FLEX2"
XOR_HTML = "<p>You can only register for one of this event's blocks.</p>" +
    "<p>Which block do you want to register for?</p>";
OR_HTML = "<p>You can register for both blocks or just one block for this event. If you want to register for both, " +
    "you can select it a second time.</p>" +
    "<p>Which block do you want to register for?</p>"
AND_HTML = "<p>This event requires you to attend both Flex 1 and Flex 2.</p>" +
    "<p>Would you like to add this event to your registration form?</p>"
ONE_HTML = "<p>Registration for this event?</p>"
BTN_TEXT_F1 = "Add for Flex 1"
BTN_TEXT_F2 = "Add for Flex 2"
BTN_TEXT_BOTH = "Add for both Flex 1 and Flex 2";

REG_STATUS_CLEAR = "Your registration form is empty.  Click an event below to add it to your form."
REG_STATUS_BOTH = "You registration form is full.  Hit the Save Selections button to register for these events."
REG_STATUS_1_ONLY = "The Flex 2 block is empty on your registration form. Click on one of the available events below."
REG_STATUS_2_ONLY = "The Flex 1 block is empty on your registration form. Click on one of the available events below."


/**
 * Set the prompts and button text for the modal then display it.
 * @param row
 */
function whichFlexModal(row, $tr) {

    $btnConfirmFlex1.data("event-id", row.id);
    $btnConfirmFlex1.attr("href", $tr.data("flex1-register-url"))
    $btnConfirmFlex2.data("event-id", row.id);
    $btnConfirmFlex2.attr("href", $tr.data("flex2-register-url"))

    $blockConfirmModalTitle.text(row.titletext);

    var eventBlocks = row.blockselection.trim()
    if (eventBlocks == F1_OR_F2) {
        $btnConfirmFlex1.text(BTN_TEXT_F1);
        $btnConfirmFlex2.text(BTN_TEXT_F2);
        $blockConfirmModalBody.html(OR_HTML);
        $btnConfirmFlex2.show();
    }
    else if (eventBlocks == F1_XOR_F2) {
        $btnConfirmFlex1.text(BTN_TEXT_F1);
        $btnConfirmFlex2.text(BTN_TEXT_F2);
        $blockConfirmModalBody.html(XOR_HTML);
        $btnConfirmFlex2.show();
    }
    else if (eventBlocks == F1_AND_F2) {
        $blockConfirmModalBody.html(AND_HTML);
        $btnConfirmFlex1.text(BTN_TEXT_BOTH);
        $btnConfirmFlex2.hide();
    }
    else if (eventBlocks == FLEX1) {
        $blockConfirmModalBody.html(ONE_HTML);
        $btnConfirmFlex1.text(BTN_TEXT_F1);
        $btnConfirmFlex2.hide();
    }
    else if (eventBlocks == FLEX2) {
        $blockConfirmModalBody.html(ONE_HTML);
        $btnConfirmFlex1.hide();
        $btnConfirmFlex2.text(BTN_TEXT_F2);
    }
    else {// shouldn't get here
        console.log(eventBlocks)
        console.log("Block selection not understood")
        return;
    }
    $blockConfirmModal.modal();
}

// EVENTS
/**
 * When a row is clicked, open a modal dialog to confirm
 */
$table.bootstrapTable({
    onClickRow: function (row, $element, field) {
        if($element.data("event-available")!=false) {
            whichFlexModal(row, $element);
        }
    }
});

$( document ).ready(function() {
    // resolve conflict between jquery UI and Bootstrap stuff
    // http://stackoverflow.com/questions/13731400/jqueryui-tooltips-are-competing-with-twitter-bootstrap
    $.widget.bridge('uibutton', $.ui.button);
    $.widget.bridge('uitooltip', $.ui.tooltip);

    $( document ).uitooltip({
        items: '[data-event-available="false"]',
        content: function() {
            var $row = $(this);
            return $row.data("tooltip-title");
        },
        hide: false,
    });
});

//if IE11
// $( document ).ready(function() {
//     var ua = window.navigator.userAgent;
//     var msie = ua.indexOf("MSIE ");
//
//     if (msie > 0 || !!navigator.userAgent.match(/Trident.*rv\:11\./))  // If Internet Explorer, return version number
//     {
//         $(".img-responsive-50").addClass("img-responsive-50-ie11-hack").removeClass("img-responsive-50");
//         $(".img-responsive").addClass("img-responsive-ie11-hack").removeClass("img-responsive");;
//     }
//
//     return false;
// });
