pipeline{
    agent any
    environment{
        IMAGE_NAME= "ctslab/pms"
        IMAGE_TAG= "${BUILD_ID}"
    }

    stages{
        stage('Build Docker Image'){
            steps{
                bat "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
            }
        }

        stage('Verify Image'){
            steps{
                bat "docker image inspect ${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }

        stage('Docker Login'){
            steps{
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]){
                    bat "docker login -u %DOCKER_USER% -p %DOCKER_PASS%"
                }
            }
        }

        stage('Push Image'){
            steps{
                bat "docker push ${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }

        stage("Verify image Push"){
            steps{
                bat "docker pull ${IMAGE_NAME}:${IMAGE_TAG}"
            }
        }
    }

    post{
        success{
            echo "Pipeline build successfully"
        }

        failure{
            echo "Pipeline failed"
        }
    }
}