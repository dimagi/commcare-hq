<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
	<title>nyroModal :: Demo</title>
	<link rel="stylesheet" href="styles/nyroModal.css" type="text/css" media="screen" />
	<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/jquery/1.3.2/jquery.min.js"></script>
	<script type="text/javascript" src="js/jquery.nyroModal-1.5.5.pack.js"></script>
</head>
<body>
<?php
$debug = '
GET Var: '.print_r($_GET, 1).'<hr />
POST Var: '.print_r($_POST, 1).'<hr />
FILES Files: '.print_r($_FILES, 1).'<hr />';
?>
<?php echo $debug ?>

You can whatever you want in the ajax request.<br />
You can create easyly :<br />
<a href="demo.php" class="nyroModalClose">close link</a><br />
<button class="nyroModalClose">close button</button><br />
<a href="demoSent.php" class="nyroModal">new modal</a><br />
<form class="nyroModal" method="post" action="demoSent.php">
		<input type="text" name="fromAjax" />
		<input type="submit" value="new modal from a form" />
</form><br />
<a href="#" class="resizeLink">Resize Modal</a>

<br />
<br />

<div id="test">
	<?php if ($_GET['nyroModalSel'] == 'test' || $_POST['nyroModalSel'] == 'test'): ?>
		<?php echo $debug ?>
		<script type="text/javascript">
		$(function() {
			$.nyroModalSettings({height: 200, width: 200});
		});
		</script>
	<?php endif; ?>
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
	Only this content will be shown if the hash is passed.<br />
</div>
<hr />
<div id="blabla">
	<?php if ($_GET['nyroModalSel'] == 'blabla' || $_POST['nyroModalSel'] == 'blabla'): ?>
		<?php echo $debug ?>
		<script type="text/javascript">
		$(function() {
			$.nyroModalSettings({height: 250, width: 700});
		});
		</script>
	<?php endif; ?>
	Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla
	Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla
	Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla
	Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla
	Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla
	Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla Bla
</div>

<script type="text/javascript">
$(function() {
	$.nyroModalSettings({height: 500, width: 500});
});
</script>

</body>
</html>