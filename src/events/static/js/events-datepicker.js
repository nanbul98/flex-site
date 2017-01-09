function WednesdaysOnly(date) {
  var day = date.getDay();
  if (day == 3) //Wednesday = 3
    return [true]
  else
    return [false]
}

$(document).ready(function () {
  var dateInputId = $('#event-datepicker').data("date-input-id");
  var $dateInput = $("#"+dateInputId);

  if ($dateInput.length == 0 )
      $dateInput = $('#datepicker');

  // console.log($dateInput)

  $dateInput.datepicker({
    dateFormat: 'yy-mm-dd',
    showOtherMonths: true,
    selectOtherMonths: true,
    onSelect: function (dateText, inst) {
      $('#filter_form').submit(); // <-- SUBMIT
    },
    beforeShowDay: WednesdaysOnly,

  });

  //Open calendar if calendar icon is selected
  $( "#datepicker-label" ).click(function() {
    $( "#datepicker" ).focus();
  });

  //check date
  $('#id_date').change(function() {
    console.log("Date changed");
  });
  // $(document).on("change", "#datepicker", function () {
  //   $.post( "ajax/test.html", function( date, block ) {
  //     $( ".result" ).html( date, block );
  //   });
  // })
});
