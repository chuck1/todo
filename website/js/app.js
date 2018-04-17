
class Application
{
	constructor() {
	}
	treeGetBranch(tree, task_id) {
		for(var task_id1 in tree)
		{
			if(tree.hasOwnProperty(task_id1))
			{
				var branch = tree[task_id1];

				if(task_id1 == task_id) return branch;

				branch = treeGetBranch(branch.children, task_id);

				if(branch) return branch;
			}
		}
		return null;
	}
	read_tasks(filter_string) {

		return new Promise((resolve, reject) => {

			var success = (result) =>
			{
				console.log('Response:');
				console.log(result);

				var tasks = [];
				var data = result[0];

				data.tasks.forEach(function(task) {
					tasks.push(new Task(task));
				});

				// store so we can later navigate to root
				//myApp.tasks = tasks;

				resolve(tasks);
			};

			callAPI(
					[{
						"command": "list 1",
						"filter_string": filter_string,
					}],
					success,
					function ajaxError(jqXHR, textStatus, errorThrown) {
						console.error('Error requesting ride: ', textStatus, ', Details: ', errorThrown);
						console.error('Response: ', jqXHR.responseText);
						alert('An error occured when requesting your unicorn:\n' + jqXHR.responseText);
					});
		});
	}
}
